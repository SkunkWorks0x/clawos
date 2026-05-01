// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {ClawURegistry} from "../src/ClawURegistry.sol";
import {ClawUClassroom} from "../src/ClawUClassroom.sol";
import {ClawUTreasury} from "../src/ClawUTreasury.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract ClawUClassroomTest is Test {
    ClawURegistry public registry;
    ClawUClassroom public classroom;
    ClawUTreasury public treasury;
    MockUSDC public usdc;

    address public chancellor = makeAddr("chancellor");
    address public professor = makeAddr("professor");
    address public student1 = makeAddr("student1");
    address public student2 = makeAddr("student2");
    address public nobody = makeAddr("nobody");

    uint256 constant BOND = 10e6;      // $10
    uint256 constant CLASS_FEE = 10e6; // $10

    function setUp() public {
        usdc = new MockUSDC();

        // --- Deploy Registry (UUPS proxy) ---
        ClawURegistry impl = new ClawURegistry();
        bytes memory initData = abi.encodeCall(
            ClawURegistry.initialize,
            (address(usdc), chancellor)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);
        registry = ClawURegistry(address(proxy));

        // --- Deploy Treasury ---
        treasury = new ClawUTreasury(address(usdc), chancellor);

        // --- Deploy Classroom ---
        classroom = new ClawUClassroom(address(usdc), address(registry), chancellor);

        // --- Wire: set treasury on Classroom ---
        vm.prank(chancellor);
        classroom.setTreasury(address(treasury));

        // --- Grant Classroom the CHANCELLOR_ROLE on Registry ---
        // so attestSuccess → issueCredential works
        // NOTE: cache role hash first — vm.prank applies to the NEXT external call,
        // and registry.CHANCELLOR_ROLE() is itself an external call that would consume it.
        bytes32 chancellorRole = registry.CHANCELLOR_ROLE();
        vm.prank(chancellor);
        registry.grantRole(chancellorRole, address(classroom));

        // --- Enroll professor (rank 0 → promote to 1) ---
        usdc.mint(professor, 10_000e6);
        vm.prank(professor);
        usdc.approve(address(registry), type(uint256).max);
        vm.prank(professor);
        registry.enroll(BOND, "acp-prof-job");
        vm.prank(chancellor);
        registry.promote(professor, 1);

        // --- Enroll students ---
        _enrollStudent(student1);
        _enrollStudent(student2);
    }

    function _enrollStudent(address student) internal {
        usdc.mint(student, 10_000e6);
        vm.prank(student);
        usdc.approve(address(registry), type(uint256).max);
        vm.prank(student);
        usdc.approve(address(classroom), type(uint256).max);
        vm.prank(student);
        registry.enroll(BOND, "acp-student-job");
    }

    function _createDefaultClass() internal returns (uint64) {
        vm.prank(professor);
        return classroom.createClass("QmTestCid123", CLASS_FEE, 60);
    }

    function _attendAndSubmitProof(address student, uint64 classId) internal {
        vm.prank(student);
        classroom.attendClass(classId);
        vm.prank(student);
        classroom.submitProof(classId, keccak256("result-hash"), "acp-challenge-001");
    }

    // =====================================================================
    //  CREATE CLASS
    // =====================================================================

    function test_createClass() public {
        uint64 classId = _createDefaultClass();
        assertEq(classId, 0);

        ClawUClassroom.Class memory c = classroom.getClass(classId);
        assertEq(c.professor, professor);
        assertEq(c.fee, CLASS_FEE);
        assertEq(c.minPassScore, 60);
        assertEq(c.studentCount, 0);
        assertGt(c.createdAt, 0);
    }

    function test_createClass_increments_id() public {
        uint64 id0 = _createDefaultClass();
        assertEq(id0, 0);

        // Warp past cooldown for second class
        vm.warp(block.timestamp + 10 days + 1);
        vm.prank(professor);
        uint64 id1 = classroom.createClass("QmSecondCid", CLASS_FEE, 70);
        assertEq(id1, 1);
    }

    function test_createClass_emits_event() public {
        vm.expectEmit(true, true, false, false);
        emit ClawUClassroom.ClassCreated(0, professor);

        vm.prank(professor);
        classroom.createClass("QmTestCid123", CLASS_FEE, 60);
    }

    function test_createClass_reverts_not_professor() public {
        vm.prank(student1);
        vm.expectRevert(ClawUClassroom.NotProfessor.selector);
        classroom.createClass("QmBadCid", CLASS_FEE, 60);
    }

    function test_createClass_reverts_not_enrolled() public {
        vm.prank(nobody);
        vm.expectRevert(ClawUClassroom.NotProfessor.selector);
        classroom.createClass("QmBadCid", CLASS_FEE, 60);
    }

    function test_createClass_reverts_fee_too_low() public {
        vm.prank(professor);
        vm.expectRevert(
            abi.encodeWithSelector(ClawUClassroom.FeeTooLow.selector, 5e6, 10e6)
        );
        classroom.createClass("QmBadCid", 5e6, 60);
    }

    function test_createClass_reverts_cooldown() public {
        _createDefaultClass();

        // Try immediately — should fail
        vm.prank(professor);
        vm.expectRevert(); // ClassCooldownActive
        classroom.createClass("QmSecondCid", CLASS_FEE, 60);
    }

    function test_createClass_succeeds_after_cooldown() public {
        _createDefaultClass();

        vm.warp(block.timestamp + 10 days + 1);
        vm.prank(professor);
        uint64 id = classroom.createClass("QmSecondCid", CLASS_FEE, 70);
        assertEq(id, 1);
    }

    // =====================================================================
    //  ATTEND CLASS
    // =====================================================================

    function test_attendClass() public {
        uint64 classId = _createDefaultClass();

        vm.prank(student1);
        classroom.attendClass(classId);

        ClawUClassroom.Attendance memory a = classroom.getAttendance(student1, classId);
        assertEq(a.student, student1);
        assertEq(a.classId, classId);
        assertGt(a.attendedAt, 0);
        assertFalse(a.attested);

        // Student count incremented
        ClawUClassroom.Class memory c = classroom.getClass(classId);
        assertEq(c.studentCount, 1);
    }

    function test_attendClass_fee_split() public {
        uint64 classId = _createDefaultClass();
        uint256 studentBalBefore = usdc.balanceOf(student1);

        vm.prank(student1);
        classroom.attendClass(classId);

        // Student paid full fee
        assertEq(usdc.balanceOf(student1), studentBalBefore - CLASS_FEE);

        // Professor claimable: 70% = $7
        assertEq(classroom.professorClaimable(professor), 7e6);

        // Treasury: 20% = $2
        assertEq(treasury.treasuryBalance(), 2e6);

        // Quality fund: 10% = $1
        assertEq(treasury.qualityFundBalance(), 1e6);

        // Verify USDC location: $7 in classroom (prof claimable), $3 in treasury
        assertEq(usdc.balanceOf(address(classroom)), 7e6);
        assertEq(usdc.balanceOf(address(treasury)), 3e6);
    }

    function test_attendClass_multiple_students() public {
        uint64 classId = _createDefaultClass();

        vm.prank(student1);
        classroom.attendClass(classId);

        vm.prank(student2);
        usdc.approve(address(classroom), type(uint256).max);
        vm.prank(student2);
        classroom.attendClass(classId);

        ClawUClassroom.Class memory c = classroom.getClass(classId);
        assertEq(c.studentCount, 2);

        // Professor earned 70% of two fees = $14
        assertEq(classroom.professorClaimable(professor), 14e6);
        // Treasury: 2 × $2 = $4
        assertEq(treasury.treasuryBalance(), 4e6);
        // Quality: 2 × $1 = $2
        assertEq(treasury.qualityFundBalance(), 2e6);
    }

    function test_attendClass_emits_event() public {
        uint64 classId = _createDefaultClass();

        vm.expectEmit(true, true, false, false);
        emit ClawUClassroom.ClassAttended(classId, student1);

        vm.prank(student1);
        classroom.attendClass(classId);
    }

    function test_attendClass_reverts_not_enrolled() public {
        uint64 classId = _createDefaultClass();

        vm.prank(nobody);
        vm.expectRevert(ClawUClassroom.NotEnrolled.selector);
        classroom.attendClass(classId);
    }

    function test_attendClass_reverts_class_not_found() public {
        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.ClassNotFound.selector, 99));
        classroom.attendClass(99);
    }

    function test_attendClass_reverts_duplicate() public {
        uint64 classId = _createDefaultClass();

        vm.prank(student1);
        classroom.attendClass(classId);

        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.AlreadyAttending.selector, classId));
        classroom.attendClass(classId);
    }

    function test_attendClass_reverts_treasury_not_set() public {
        // Deploy fresh classroom without treasury
        ClawUClassroom bare = new ClawUClassroom(address(usdc), address(registry), chancellor);

        // Professor creates class (createClass checks rank via shared registry, not Classroom ACL)
        vm.prank(professor);
        uint64 classId = bare.createClass("QmCid", CLASS_FEE, 60);

        vm.prank(student1);
        usdc.approve(address(bare), type(uint256).max);
        vm.prank(student1);
        vm.expectRevert(ClawUClassroom.TreasuryNotSet.selector);
        bare.attendClass(classId);
    }

    // =====================================================================
    //  SUBMIT PROOF
    // =====================================================================

    function test_submitProof() public {
        uint64 classId = _createDefaultClass();
        vm.prank(student1);
        classroom.attendClass(classId);

        bytes32 proofHash = keccak256("my-proof");
        vm.prank(student1);
        classroom.submitProof(classId, proofHash, "acp-job-456");

        ClawUClassroom.Attendance memory a = classroom.getAttendance(student1, classId);
        assertEq(a.proofHash, proofHash);
    }

    function test_submitProof_emits_event() public {
        uint64 classId = _createDefaultClass();
        vm.prank(student1);
        classroom.attendClass(classId);

        bytes32 proofHash = keccak256("my-proof");
        vm.expectEmit(true, true, false, true);
        emit ClawUClassroom.ProofSubmitted(classId, student1, proofHash);

        vm.prank(student1);
        classroom.submitProof(classId, proofHash, "acp-job-456");
    }

    function test_submitProof_reverts_not_attending() public {
        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.NotAttending.selector, 0));
        classroom.submitProof(0, keccak256("proof"), "job");
    }

    function test_submitProof_reverts_after_attestation() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        // Attest
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        // Try to resubmit proof
        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.AlreadyAttested.selector, classId));
        classroom.submitProof(classId, keccak256("new-proof"), "new-job");
    }

    // =====================================================================
    //  ATTEST SUCCESS
    // =====================================================================

    function test_attestSuccess_passing() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        ClawUClassroom.Attendance memory a = classroom.getAttendance(student1, classId);
        assertEq(a.score, 85);
        assertTrue(a.attested);

        // Credential issued on Registry (score >= minPassScore of 60)
        ClawURegistry.Credential memory cred = registry.getCredential(student1, classId);
        assertEq(cred.owner, student1);
        assertEq(cred.score, 85);
        assertEq(cred.classId, classId);
    }

    function test_attestSuccess_failing_score() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        // Score 40 < minPassScore 60 → no credential
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 40);

        ClawUClassroom.Attendance memory a = classroom.getAttendance(student1, classId);
        assertEq(a.score, 40);
        assertTrue(a.attested);

        // No credential issued
        ClawURegistry.Credential memory cred = registry.getCredential(student1, classId);
        assertEq(cred.owner, address(0));
    }

    function test_attestSuccess_exact_pass_score() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        // Score exactly == minPassScore → should pass
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 60);

        ClawURegistry.Credential memory cred = registry.getCredential(student1, classId);
        assertEq(cred.owner, student1);
        assertEq(cred.score, 60);
    }

    function test_attestSuccess_emits_event() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        vm.expectEmit(true, true, false, true);
        emit ClawUClassroom.Attested(classId, student1, 85);

        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);
    }

    function test_attestSuccess_reverts_not_chancellor() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        vm.prank(nobody);
        vm.expectRevert();
        classroom.attestSuccess(classId, student1, 85);
    }

    function test_attestSuccess_reverts_no_proof() public {
        uint64 classId = _createDefaultClass();
        vm.prank(student1);
        classroom.attendClass(classId);
        // No proof submitted

        vm.prank(chancellor);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.ProofNotSubmitted.selector, classId));
        classroom.attestSuccess(classId, student1, 85);
    }

    function test_attestSuccess_reverts_double_attest() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);

        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        vm.prank(chancellor);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.AlreadyAttested.selector, classId));
        classroom.attestSuccess(classId, student1, 90);
    }

    // =====================================================================
    //  SUBMIT RATING
    // =====================================================================

    function test_submitRating() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        vm.prank(student1);
        classroom.submitRating(classId, 5);

        ClawUClassroom.Class memory c = classroom.getClass(classId);
        assertEq(c.totalRating, 5);
        assertEq(c.ratingCount, 1);
    }

    function test_submitRating_emits_event() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        vm.expectEmit(true, true, false, true);
        emit ClawUClassroom.Rated(classId, student1, 4);

        vm.prank(student1);
        classroom.submitRating(classId, 4);
    }

    function test_submitRating_reverts_invalid_zero() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        vm.prank(student1);
        vm.expectRevert(ClawUClassroom.InvalidRating.selector);
        classroom.submitRating(classId, 0);
    }

    function test_submitRating_reverts_invalid_six() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        vm.prank(student1);
        vm.expectRevert(ClawUClassroom.InvalidRating.selector);
        classroom.submitRating(classId, 6);
    }

    function test_submitRating_reverts_not_attested() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);
        // NOT attested yet

        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.NotAttested.selector, classId));
        classroom.submitRating(classId, 5);
    }

    function test_submitRating_reverts_double_rating() public {
        uint64 classId = _createDefaultClass();
        _attendAndSubmitProof(student1, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        // First rating succeeds
        vm.prank(student1);
        classroom.submitRating(classId, 4);

        // Second rating from same student reverts
        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.AlreadyRated.selector, classId));
        classroom.submitRating(classId, 5);

        // Verify totals unchanged after revert
        ClawUClassroom.Class memory c = classroom.getClass(classId);
        assertEq(c.totalRating, 4);
        assertEq(c.ratingCount, 1);
    }

    function test_submitRating_different_students_both_succeed() public {
        uint64 classId = _createDefaultClass();

        // student1 attends, proves, gets attested
        _attendAndSubmitProof(student1, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        // student2 attends, proves, gets attested
        vm.prank(student2);
        usdc.approve(address(classroom), type(uint256).max);
        _attendAndSubmitProof(student2, classId);
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student2, 90);

        // Both students can rate
        vm.prank(student1);
        classroom.submitRating(classId, 4);
        vm.prank(student2);
        classroom.submitRating(classId, 5);

        ClawUClassroom.Class memory c = classroom.getClass(classId);
        assertEq(c.totalRating, 9);
        assertEq(c.ratingCount, 2);
    }

    function test_submitRating_reverts_not_attending() public {
        _createDefaultClass();

        vm.prank(student1);
        vm.expectRevert(abi.encodeWithSelector(ClawUClassroom.NotAttending.selector, 0));
        classroom.submitRating(0, 5);
    }

    // =====================================================================
    //  CLAIM FEES (PULL PATTERN)
    // =====================================================================

    function test_claimFees() public {
        uint64 classId = _createDefaultClass();

        vm.prank(student1);
        classroom.attendClass(classId);

        uint256 profBalBefore = usdc.balanceOf(professor);

        // Professor claims 70% = $7
        vm.prank(professor);
        classroom.claimFees();

        assertEq(usdc.balanceOf(professor), profBalBefore + 7e6);
        assertEq(classroom.professorClaimable(professor), 0);
    }

    function test_claimFees_accumulates_multiple_students() public {
        uint64 classId = _createDefaultClass();

        vm.prank(student1);
        classroom.attendClass(classId);

        vm.prank(student2);
        usdc.approve(address(classroom), type(uint256).max);
        vm.prank(student2);
        classroom.attendClass(classId);

        // Accumulated: 2 × $7 = $14
        assertEq(classroom.professorClaimable(professor), 14e6);

        uint256 profBalBefore = usdc.balanceOf(professor);
        vm.prank(professor);
        classroom.claimFees();

        assertEq(usdc.balanceOf(professor), profBalBefore + 14e6);
        assertEq(classroom.professorClaimable(professor), 0);
    }

    function test_claimFees_emits_event() public {
        uint64 classId = _createDefaultClass();
        vm.prank(student1);
        classroom.attendClass(classId);

        vm.expectEmit(true, false, false, true);
        emit ClawUClassroom.FeesClaimed(professor, 7e6);

        vm.prank(professor);
        classroom.claimFees();
    }

    function test_claimFees_reverts_nothing() public {
        vm.prank(professor);
        vm.expectRevert(ClawUClassroom.NothingToClaim.selector);
        classroom.claimFees();
    }

    function test_claimFees_reverts_double_claim() public {
        uint64 classId = _createDefaultClass();
        vm.prank(student1);
        classroom.attendClass(classId);

        vm.prank(professor);
        classroom.claimFees();

        vm.prank(professor);
        vm.expectRevert(ClawUClassroom.NothingToClaim.selector);
        classroom.claimFees();
    }

    // =====================================================================
    //  FULL CLASS SESSION FLOW (end-to-end)
    // =====================================================================

    function test_fullClassFlow() public {
        // 1. Professor creates class
        uint64 classId = _createDefaultClass();

        // 2. Student attends (pays $10)
        uint256 studentBal = usdc.balanceOf(student1);
        vm.prank(student1);
        classroom.attendClass(classId);
        assertEq(usdc.balanceOf(student1), studentBal - CLASS_FEE);

        // 3. Student submits proof
        bytes32 proofHash = keccak256("applied-challenge-result");
        vm.prank(student1);
        classroom.submitProof(classId, proofHash, "acp-real-job-789");

        // 4. Chancellor attests with passing score
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 92);

        // 5. Verify credential on Registry
        ClawURegistry.Credential memory cred = registry.getCredential(student1, classId);
        assertEq(cred.owner, student1);
        assertEq(cred.score, 92);

        // 6. Student rates class
        vm.prank(student1);
        classroom.submitRating(classId, 5);

        // 7. Professor claims fees
        uint256 profBal = usdc.balanceOf(professor);
        vm.prank(professor);
        classroom.claimFees();
        assertEq(usdc.balanceOf(professor), profBal + 7e6);

        // 8. Verify treasury balances
        assertEq(treasury.treasuryBalance(), 2e6);
        assertEq(treasury.qualityFundBalance(), 1e6);
    }

    // =====================================================================
    //  FEE SPLIT FUZZ
    // =====================================================================

    function testFuzz_feeSplit(uint256 fee) public {
        fee = bound(fee, 10e6, 1_000e6);

        // Professor creates class with arbitrary fee
        vm.prank(professor);
        uint64 classId = classroom.createClass("QmFuzzCid", fee, 50);

        // Fund student enough
        usdc.mint(student1, fee);

        uint256 profClaimBefore = classroom.professorClaimable(professor);
        uint256 treasuryBefore = treasury.treasuryBalance();
        uint256 qualityBefore = treasury.qualityFundBalance();

        vm.prank(student1);
        classroom.attendClass(classId);

        uint256 expectedProf = (fee * 70) / 100;
        uint256 expectedTreasury = (fee * 20) / 100;
        uint256 expectedQuality = fee - expectedProf - expectedTreasury;

        assertEq(classroom.professorClaimable(professor) - profClaimBefore, expectedProf);
        assertEq(treasury.treasuryBalance() - treasuryBefore, expectedTreasury);
        assertEq(treasury.qualityFundBalance() - qualityBefore, expectedQuality);
    }

    // =====================================================================
    //  RATE LIMITING FUZZ
    // =====================================================================

    function testFuzz_cooldown(uint256 elapsed) public {
        _createDefaultClass();

        elapsed = bound(elapsed, 0, 20 days);
        vm.warp(block.timestamp + elapsed);

        if (elapsed < 10 days) {
            vm.prank(professor);
            vm.expectRevert();
            classroom.createClass("QmNext", CLASS_FEE, 60);
        } else {
            vm.prank(professor);
            uint64 id = classroom.createClass("QmNext", CLASS_FEE, 60);
            assertEq(id, 1);
        }
    }

    // =====================================================================
    //  SET TREASURY
    // =====================================================================

    function test_setTreasury() public {
        address newTreasury = makeAddr("newTreasury");
        vm.prank(chancellor);
        classroom.setTreasury(newTreasury);
        assertEq(address(classroom.treasury()), newTreasury);
    }

    function test_setTreasury_reverts_not_chancellor() public {
        vm.prank(nobody);
        vm.expectRevert();
        classroom.setTreasury(makeAddr("bad"));
    }

    function test_setTreasury_reverts_zero() public {
        vm.prank(chancellor);
        vm.expectRevert(ClawUClassroom.ZeroAddress.selector);
        classroom.setTreasury(address(0));
    }
}
