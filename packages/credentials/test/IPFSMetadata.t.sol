// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {ClawURegistry} from "../src/ClawURegistry.sol";
import {ClawUClassroom} from "../src/ClawUClassroom.sol";
import {ClawUTreasury} from "../src/ClawUTreasury.sol";
import {MockUSDC} from "./mocks/MockUSDC.sol";
import {CidUtils} from "../src/libraries/CidUtils.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract IPFSMetadataTest is Test {
    ClawURegistry public registry;
    ClawUClassroom public classroom;
    ClawUTreasury public treasury;
    MockUSDC public usdc;

    address public chancellor = makeAddr("chancellor");
    address public professor = makeAddr("professor");
    address public student1 = makeAddr("student1");
    address public nobody = makeAddr("nobody");

    string constant VALID_CID = "QmYwAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx";
    string constant VALID_CIDV1 = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";
    string constant INVALID_CID = "not-a-valid-cid";

    uint256 constant BOND = 10e6;
    uint256 constant CLASS_FEE = 10e6;

    function setUp() public {
        usdc = new MockUSDC();

        // Deploy Registry (UUPS proxy)
        ClawURegistry impl = new ClawURegistry();
        bytes memory initData = abi.encodeCall(
            ClawURegistry.initialize,
            (address(usdc), chancellor)
        );
        ERC1967Proxy proxy = new ERC1967Proxy(address(impl), initData);
        registry = ClawURegistry(address(proxy));

        // Deploy Treasury
        treasury = new ClawUTreasury(address(usdc), chancellor);

        // Deploy Classroom
        classroom = new ClawUClassroom(address(usdc), address(registry), chancellor);

        // Wire treasury
        vm.prank(chancellor);
        classroom.setTreasury(address(treasury));

        // Grant Classroom CHANCELLOR_ROLE on Registry
        bytes32 chancellorRole = registry.CHANCELLOR_ROLE();
        vm.prank(chancellor);
        registry.grantRole(chancellorRole, address(classroom));

        // Enroll professor
        usdc.mint(professor, 10_000e6);
        vm.prank(professor);
        usdc.approve(address(registry), type(uint256).max);
        vm.prank(professor);
        registry.enroll(BOND, "acp-prof-job");
        vm.prank(chancellor);
        registry.promote(professor, 1);

        // Enroll student
        usdc.mint(student1, 10_000e6);
        vm.prank(student1);
        usdc.approve(address(registry), type(uint256).max);
        vm.prank(student1);
        usdc.approve(address(classroom), type(uint256).max);
        vm.prank(student1);
        registry.enroll(BOND, "acp-student-job");
    }

    // =====================================================================
    //  ISSUE CREDENTIAL WITH METADATA (CIDv0)
    // =====================================================================

    function test_issueCredentialWithMetadata_v0() public {
        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(1, student1, 85, VALID_CID);

        ClawURegistry.Credential memory cred = registry.getCredential(student1, 1);
        assertEq(cred.owner, student1);
        assertEq(cred.score, 85);
        assertEq(cred.classId, 1);
        assertEq(keccak256(bytes(cred.metadataCid)), keccak256(bytes(VALID_CID)));
    }

    function test_issueCredentialWithMetadata_v1() public {
        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(2, student1, 90, VALID_CIDV1);

        ClawURegistry.Credential memory cred = registry.getCredential(student1, 2);
        assertEq(keccak256(bytes(cred.metadataCid)), keccak256(bytes(VALID_CIDV1)));
    }

    // =====================================================================
    //  BACKWARD COMPAT: issueCredential (no CID) still works
    // =====================================================================

    function test_issueCredential_without_metadata_still_works() public {
        vm.prank(chancellor);
        registry.issueCredential(1, student1, 85);

        ClawURegistry.Credential memory cred = registry.getCredential(student1, 1);
        assertEq(cred.owner, student1);
        assertEq(cred.score, 85);
        assertEq(bytes(cred.metadataCid).length, 0); // empty CID
    }

    // =====================================================================
    //  CID STORED ON-CHAIN — RETRIEVAL
    // =====================================================================

    function test_metadataCid_stored_and_retrievable() public {
        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(42, student1, 95, VALID_CID);

        ClawURegistry.Credential memory cred = registry.getCredential(student1, 42);
        assertGt(bytes(cred.metadataCid).length, 0);

        // Verify exact CID match
        assertEq(keccak256(bytes(cred.metadataCid)), keccak256(bytes(VALID_CID)));
    }

    function test_multiple_credentials_different_cids() public {
        string memory cid1 = VALID_CID;
        string memory cid2 = VALID_CIDV1;

        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(1, student1, 85, cid1);

        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(2, student1, 90, cid2);

        ClawURegistry.Credential memory c1 = registry.getCredential(student1, 1);
        ClawURegistry.Credential memory c2 = registry.getCredential(student1, 2);

        assertEq(keccak256(bytes(c1.metadataCid)), keccak256(bytes(cid1)));
        assertEq(keccak256(bytes(c2.metadataCid)), keccak256(bytes(cid2)));
        assertTrue(keccak256(bytes(c1.metadataCid)) != keccak256(bytes(c2.metadataCid)));
    }

    // =====================================================================
    //  CID VALIDATION — ERROR PATHS
    // =====================================================================

    function test_issueCredentialWithMetadata_reverts_empty_cid() public {
        vm.prank(chancellor);
        vm.expectRevert(CidUtils.EmptyCid.selector);
        registry.issueCredentialWithMetadata(1, student1, 85, "");
    }

    function test_issueCredentialWithMetadata_reverts_short_cid() public {
        vm.prank(chancellor);
        vm.expectRevert(CidUtils.CidTooShort.selector);
        registry.issueCredentialWithMetadata(1, student1, 85, "QmTooShort");
    }

    function test_issueCredentialWithMetadata_reverts_invalid_prefix() public {
        // 46 chars with wrong prefix
        vm.prank(chancellor);
        vm.expectRevert(CidUtils.InvalidCidPrefix.selector);
        registry.issueCredentialWithMetadata(1, student1, 85, "ZzYwAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx");
    }

    function test_issueCredentialWithMetadata_reverts_bad_base58_char() public {
        // Valid length, starts with "Qm", but contains '0' (invalid base58)
        vm.prank(chancellor);
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase58Char.selector, uint8(bytes1("0"))));
        registry.issueCredentialWithMetadata(1, student1, 85, "Qm0wAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx");
    }

    // =====================================================================
    //  ACCESS CONTROL — METADATA VARIANT
    // =====================================================================

    function test_issueCredentialWithMetadata_reverts_not_chancellor() public {
        vm.prank(nobody);
        vm.expectRevert();
        registry.issueCredentialWithMetadata(1, student1, 85, VALID_CID);
    }

    function test_issueCredentialWithMetadata_reverts_not_enrolled() public {
        vm.prank(chancellor);
        vm.expectRevert(ClawURegistry.NotEnrolled.selector);
        registry.issueCredentialWithMetadata(1, nobody, 85, VALID_CID);
    }

    // =====================================================================
    //  EVENT EMISSION WITH CID
    // =====================================================================

    function test_issueCredentialWithMetadata_emits_event() public {
        vm.expectEmit(true, true, false, true);
        emit ClawURegistry.CredentialIssued(student1, 1, 85, VALID_CID);

        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(1, student1, 85, VALID_CID);
    }

    function test_issueCredential_emits_event_empty_cid() public {
        vm.expectEmit(true, true, false, true);
        emit ClawURegistry.CredentialIssued(student1, 1, 85, "");

        vm.prank(chancellor);
        registry.issueCredential(1, student1, 85);
    }

    // =====================================================================
    //  TRANSCRIPT HASH WITH METADATA
    // =====================================================================

    function test_transcript_hash_updated_with_metadata() public {
        (, , , bytes32 hashBefore, ) = registry.enrollments(student1);
        assertEq(hashBefore, bytes32(0));

        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(1, student1, 85, VALID_CID);

        (, , , bytes32 hashAfter, ) = registry.enrollments(student1);
        assertNotEq(hashAfter, bytes32(0));
    }

    // =====================================================================
    //  FULL FLOW: CLASS → ATTEST → CREDENTIAL WITH METADATA
    // =====================================================================

    function test_fullFlow_attestIssuesCredentialWithoutMetadata() public {
        // Create class
        vm.prank(professor);
        uint64 classId = classroom.createClass("QmKnowledgeModuleCid123456789012345", CLASS_FEE, 60);

        // Attend
        vm.prank(student1);
        classroom.attendClass(classId);

        // Submit proof
        vm.prank(student1);
        classroom.submitProof(classId, keccak256("challenge-result"), "acp-job-001");

        // Attest (passing score) — uses legacy issueCredential (no metadata)
        vm.prank(chancellor);
        classroom.attestSuccess(classId, student1, 85);

        // Credential issued without metadata
        ClawURegistry.Credential memory cred = registry.getCredential(student1, classId);
        assertEq(cred.owner, student1);
        assertEq(cred.score, 85);
        assertEq(bytes(cred.metadataCid).length, 0);
    }

    // =====================================================================
    //  FUZZ: CID STORAGE INTEGRITY
    // =====================================================================

    function testFuzz_credentialMetadataStored(uint8 score) public {
        vm.prank(chancellor);
        registry.issueCredentialWithMetadata(1, student1, score, VALID_CID);

        ClawURegistry.Credential memory cred = registry.getCredential(student1, 1);
        assertEq(cred.score, score);
        assertEq(keccak256(bytes(cred.metadataCid)), keccak256(bytes(VALID_CID)));
    }
}
