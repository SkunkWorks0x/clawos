// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test, console2} from "forge-std/Test.sol";
import {ClawURegistry} from "../src/ClawURegistry.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract ClawURegistryTest is Test {
    ClawURegistry public registry;
    MockUSDC public usdc;

    address public chancellor = makeAddr("chancellor");
    address public agent1 = makeAddr("agent1");
    address public agent2 = makeAddr("agent2");
    address public treasuryAddr = makeAddr("treasury");
    address public nobody = makeAddr("nobody");

    function setUp() public {
        usdc = new MockUSDC();

        // Deploy UUPS proxy
        ClawURegistry impl = new ClawURegistry();
        bytes memory initData = abi.encodeCall(
            ClawURegistry.initialize,
            (address(usdc), chancellor)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);
        registry = ClawURegistry(address(proxy));

        // Fund test agents
        usdc.mint(agent1, 1000e6); // 1000 USDC
        usdc.mint(agent2, 1000e6);

        vm.prank(agent1);
        usdc.approve(address(registry), type(uint256).max);
        vm.prank(agent2);
        usdc.approve(address(registry), type(uint256).max);

        // Set treasury
        vm.prank(chancellor);
        registry.setTreasury(treasuryAddr);
    }

    // ========== INITIALIZATION ==========

    function test_initialize() public view {
        assertEq(address(registry.usdc()), address(usdc));
        assertTrue(registry.hasRole(registry.CHANCELLOR_ROLE(), chancellor));
        assertTrue(registry.hasRole(registry.UPGRADER_ROLE(), chancellor));
        assertTrue(registry.hasRole(registry.DEFAULT_ADMIN_ROLE(), chancellor));
    }

    function test_initialize_reverts_zero_usdc() public {
        ClawURegistry impl = new ClawURegistry();
        bytes memory initData = abi.encodeCall(
            ClawURegistry.initialize,
            (address(0), chancellor)
        );
        vm.expectRevert(ClawURegistry.ZeroAddress.selector);
        new ERC1967Proxy(address(impl), initData);
    }

    function test_initialize_reverts_zero_chancellor() public {
        ClawURegistry impl = new ClawURegistry();
        bytes memory initData = abi.encodeCall(
            ClawURegistry.initialize,
            (address(usdc), address(0))
        );
        vm.expectRevert(ClawURegistry.ZeroAddress.selector);
        new ERC1967Proxy(address(impl), initData);
    }

    function test_cannot_reinitialize() public {
        vm.expectRevert();
        registry.initialize(address(usdc), chancellor);
    }

    // ========== ENROLLMENT ==========

    function test_enroll() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        (uint256 bond, uint8 rank, uint64 enrolledAt, bytes32 transcriptHash, bool active) =
            registry.enrollments(agent1);

        assertEq(bond, 10e6);
        assertEq(rank, 0); // student
        assertGt(enrolledAt, 0);
        assertEq(transcriptHash, bytes32(0));
        assertTrue(active);
        assertTrue(registry.isEnrolled(agent1));
    }

    function test_enroll_transfers_usdc() public {
        uint256 balBefore = usdc.balanceOf(agent1);

        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        assertEq(usdc.balanceOf(agent1), balBefore - 10e6);
        assertEq(usdc.balanceOf(address(registry)), 10e6);
    }

    function test_enroll_larger_bond() public {
        vm.prank(agent1);
        registry.enroll(50e6, "acp-job-456"); // $50 bond

        (uint256 bond,,,, bool active) = registry.enrollments(agent1);
        assertEq(bond, 50e6);
        assertTrue(active);
    }

    function test_enroll_emits_event() public {
        vm.expectEmit(true, false, false, true);
        emit ClawURegistry.Enrolled(agent1, 10e6);

        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");
    }

    function test_enroll_reverts_below_minimum() public {
        vm.prank(agent1);
        vm.expectRevert(
            abi.encodeWithSelector(ClawURegistry.BondTooLow.selector, 5e6, 10e6)
        );
        registry.enroll(5e6, "acp-job-123");
    }

    function test_enroll_reverts_zero_bond() public {
        vm.prank(agent1);
        vm.expectRevert(
            abi.encodeWithSelector(ClawURegistry.BondTooLow.selector, 0, 10e6)
        );
        registry.enroll(0, "acp-job-123");
    }

    function test_enroll_reverts_already_enrolled() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(agent1);
        vm.expectRevert(ClawURegistry.AlreadyEnrolled.selector);
        registry.enroll(10e6, "acp-job-456");
    }

    function test_enroll_reverts_no_approval() public {
        address noApproval = makeAddr("noApproval");
        usdc.mint(noApproval, 100e6);
        // No approval given

        vm.prank(noApproval);
        vm.expectRevert();
        registry.enroll(10e6, "acp-job-123");
    }

    function test_enroll_reverts_insufficient_balance() public {
        address poorAgent = makeAddr("poorAgent");
        usdc.mint(poorAgent, 5e6); // only $5
        vm.prank(poorAgent);
        usdc.approve(address(registry), type(uint256).max);

        vm.prank(poorAgent);
        vm.expectRevert();
        registry.enroll(10e6, "acp-job-123");
    }

    // ========== ISSUE CREDENTIAL ==========

    function test_issueCredential() public {
        // Enroll agent first
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        // Chancellor issues credential
        vm.prank(chancellor);
        registry.issueCredential(42, agent1, 85);

        ClawURegistry.Credential memory cred = registry.getCredential(agent1, 42);
        assertEq(cred.owner, agent1);
        assertEq(cred.classId, 42);
        assertEq(cred.score, 85);
        assertGt(cred.issuedAt, 0);
    }

    function test_issueCredential_updates_transcript() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(chancellor);
        registry.issueCredential(42, agent1, 85);

        (, , , bytes32 transcript1, ) = registry.enrollments(agent1);
        assertNotEq(transcript1, bytes32(0));

        // Issue second credential — transcript hash changes
        vm.prank(chancellor);
        registry.issueCredential(43, agent1, 90);

        (, , , bytes32 transcript2, ) = registry.enrollments(agent1);
        assertNotEq(transcript2, transcript1);
    }

    function test_issueCredential_emits_event() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.expectEmit(true, true, false, true);
        emit ClawURegistry.CredentialIssued(agent1, 42, 85, "");

        vm.prank(chancellor);
        registry.issueCredential(42, agent1, 85);
    }

    function test_issueCredential_reverts_not_chancellor() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(nobody);
        vm.expectRevert();
        registry.issueCredential(42, agent1, 85);
    }

    function test_issueCredential_reverts_not_enrolled() public {
        vm.prank(chancellor);
        vm.expectRevert(ClawURegistry.NotEnrolled.selector);
        registry.issueCredential(42, agent1, 85);
    }

    // ========== SLASH BOND ==========

    function test_slashBond_partial() public {
        vm.prank(agent1);
        registry.enroll(20e6, "acp-job-123");

        vm.prank(chancellor);
        registry.slashBond(agent1, 5e6);

        (uint256 bond,,,, bool active) = registry.enrollments(agent1);
        assertEq(bond, 15e6);
        assertTrue(active);
        assertEq(usdc.balanceOf(treasuryAddr), 5e6);
    }

    function test_slashBond_full_deactivates() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(chancellor);
        registry.slashBond(agent1, 10e6);

        (uint256 bond,,,, bool active) = registry.enrollments(agent1);
        assertEq(bond, 0);
        assertFalse(active);
        assertFalse(registry.isEnrolled(agent1));
        assertEq(usdc.balanceOf(treasuryAddr), 10e6);
    }

    function test_slashBond_emits_event() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.expectEmit(true, false, false, true);
        emit ClawURegistry.BondSlashed(agent1, 5e6);

        vm.prank(chancellor);
        registry.slashBond(agent1, 5e6);
    }

    function test_slashBond_reverts_not_enrolled() public {
        vm.prank(chancellor);
        vm.expectRevert(ClawURegistry.NotEnrolled.selector);
        registry.slashBond(agent1, 5e6);
    }

    function test_slashBond_reverts_exceeds_bond() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(chancellor);
        vm.expectRevert(
            abi.encodeWithSelector(ClawURegistry.InsufficientBond.selector, 10e6, 15e6)
        );
        registry.slashBond(agent1, 15e6);
    }

    function test_slashBond_reverts_not_chancellor() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(nobody);
        vm.expectRevert();
        registry.slashBond(agent1, 5e6);
    }

    // ========== PROMOTE ==========

    function test_promote() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(chancellor);
        registry.promote(agent1, 1); // professor

        (, uint8 rank,,, ) = registry.enrollments(agent1);
        assertEq(rank, 1);
    }

    function test_promote_emits_event() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.expectEmit(true, false, false, true);
        emit ClawURegistry.Promoted(agent1, 1);

        vm.prank(chancellor);
        registry.promote(agent1, 1);
    }

    function test_promote_reverts_not_enrolled() public {
        vm.prank(chancellor);
        vm.expectRevert(ClawURegistry.NotEnrolled.selector);
        registry.promote(agent1, 1);
    }

    function test_promote_reverts_not_chancellor() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(nobody);
        vm.expectRevert();
        registry.promote(agent1, 1);
    }

    // ========== RE-ENROLLMENT AFTER SLASH ==========

    function test_reenroll_after_full_slash() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(chancellor);
        registry.slashBond(agent1, 10e6); // fully slashed

        assertFalse(registry.isEnrolled(agent1));

        // Can re-enroll
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-789");

        assertTrue(registry.isEnrolled(agent1));
    }

    // ========== MULTIPLE AGENTS ==========

    function test_multiple_agents_enroll() public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-1");

        vm.prank(agent2);
        registry.enroll(20e6, "acp-job-2");

        (uint256 bond1,,,, ) = registry.enrollments(agent1);
        (uint256 bond2,,,, ) = registry.enrollments(agent2);
        assertEq(bond1, 10e6);
        assertEq(bond2, 20e6);
        assertEq(usdc.balanceOf(address(registry)), 30e6);
    }

    // ========== FUZZ TESTS ==========

    function testFuzz_enroll_bond(uint256 bondAmount) public {
        bondAmount = bound(bondAmount, 10e6, 500e6);
        usdc.mint(agent1, bondAmount); // ensure sufficient

        vm.prank(agent1);
        registry.enroll(bondAmount, "fuzz-job");

        (uint256 bond,,,, bool active) = registry.enrollments(agent1);
        assertEq(bond, bondAmount);
        assertTrue(active);
    }

    function testFuzz_slashBond(uint256 slashAmount) public {
        vm.prank(agent1);
        registry.enroll(100e6, "acp-job-123");

        slashAmount = bound(slashAmount, 1, 100e6);

        vm.prank(chancellor);
        registry.slashBond(agent1, slashAmount);

        (uint256 bond,,,, bool active) = registry.enrollments(agent1);
        assertEq(bond, 100e6 - slashAmount);
        if (slashAmount == 100e6) {
            assertFalse(active);
        } else {
            assertTrue(active);
        }
    }

    function testFuzz_issueCredential_score(uint8 score) public {
        vm.prank(agent1);
        registry.enroll(10e6, "acp-job-123");

        vm.prank(chancellor);
        registry.issueCredential(1, agent1, score);

        ClawURegistry.Credential memory cred = registry.getCredential(agent1, 1);
        assertEq(cred.score, score);
    }

    // ========== SET TREASURY ==========

    function test_setTreasury() public {
        address newTreasury = makeAddr("newTreasury");
        vm.prank(chancellor);
        registry.setTreasury(newTreasury);
        assertEq(registry.treasury(), newTreasury);
    }

    function test_setTreasury_reverts_not_chancellor() public {
        vm.prank(nobody);
        vm.expectRevert();
        registry.setTreasury(makeAddr("newTreasury"));
    }

    // ========== UUPS UPGRADE ==========

    function test_upgrade_by_upgrader() public {
        ClawURegistry newImpl = new ClawURegistry();

        vm.prank(chancellor);
        registry.upgradeToAndCall(address(newImpl), "");

        // Still works after upgrade
        vm.prank(agent1);
        registry.enroll(10e6, "post-upgrade");
        assertTrue(registry.isEnrolled(agent1));
    }

    function test_upgrade_reverts_not_upgrader() public {
        ClawURegistry newImpl = new ClawURegistry();

        vm.prank(nobody);
        vm.expectRevert();
        registry.upgradeToAndCall(address(newImpl), "");
    }
}
