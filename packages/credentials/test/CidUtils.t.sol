// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {CidUtils} from "../src/libraries/CidUtils.sol";

/// @notice Wrapper to expose library functions for testing
contract CidUtilsHarness {
    function validateCid(string calldata cid) external pure {
        CidUtils.validateCid(cid);
    }

    function isValidCid(string calldata cid) external pure returns (bool) {
        return CidUtils.isValidCid(cid);
    }
}

contract CidUtilsTest is Test {
    CidUtilsHarness public harness;

    // --- Real-format test CIDs ---
    // CIDv0: "Qm" + 44 base58 chars = 46 chars total
    string constant VALID_CIDV0 = "QmYwAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx";
    // CIDv1: "bafy" prefix + base32 lower chars, >= 59 chars
    string constant VALID_CIDV1 = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi";

    function setUp() public {
        harness = new CidUtilsHarness();
    }

    // =====================================================================
    //  VALIDATE CID — HAPPY PATHS
    // =====================================================================

    function test_validateCid_v0() public view {
        harness.validateCid(VALID_CIDV0);
    }

    function test_validateCid_v1() public view {
        harness.validateCid(VALID_CIDV1);
    }

    function test_isValidCid_v0_returns_true() public view {
        assertTrue(harness.isValidCid(VALID_CIDV0));
    }

    function test_isValidCid_v1_returns_true() public view {
        assertTrue(harness.isValidCid(VALID_CIDV1));
    }

    // =====================================================================
    //  VALIDATE CID — ERROR PATHS
    // =====================================================================

    function test_validateCid_reverts_empty() public {
        vm.expectRevert(CidUtils.EmptyCid.selector);
        harness.validateCid("");
    }

    function test_validateCid_reverts_too_short() public {
        vm.expectRevert(CidUtils.CidTooShort.selector);
        harness.validateCid("QmShort");
    }

    function test_validateCid_reverts_too_long() public {
        // 129 chars starting with "bafy"
        bytes memory longCid = new bytes(129);
        longCid[0] = "b";
        longCid[1] = "a";
        longCid[2] = "f";
        longCid[3] = "y";
        for (uint256 i = 4; i < 129; ++i) {
            longCid[i] = "a"; // valid base32
        }
        vm.expectRevert(CidUtils.CidTooLong.selector);
        harness.validateCid(string(longCid));
    }

    function test_validateCid_reverts_invalid_prefix() public {
        // 46 chars but starts with "Xm" instead of "Qm"
        vm.expectRevert(CidUtils.InvalidCidPrefix.selector);
        harness.validateCid("XmYwAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx");
    }

    function test_validateCid_v0_reverts_invalid_base58_char_zero() public {
        // '0' is not in base58 alphabet — replace char at position 2
        bytes memory bad = bytes(VALID_CIDV0);
        bad[2] = "0"; // invalid base58
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase58Char.selector, uint8(bytes1("0"))));
        harness.validateCid(string(bad));
    }

    function test_validateCid_v0_reverts_invalid_base58_char_I() public {
        bytes memory bad = bytes(VALID_CIDV0);
        bad[2] = "I"; // 'I' excluded from base58
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase58Char.selector, uint8(bytes1("I"))));
        harness.validateCid(string(bad));
    }

    function test_validateCid_v0_reverts_invalid_base58_char_O() public {
        bytes memory bad = bytes(VALID_CIDV0);
        bad[2] = "O"; // 'O' excluded from base58
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase58Char.selector, uint8(bytes1("O"))));
        harness.validateCid(string(bad));
    }

    function test_validateCid_v0_reverts_invalid_base58_char_l() public {
        bytes memory bad = bytes(VALID_CIDV0);
        bad[2] = "l"; // 'l' excluded from base58
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase58Char.selector, uint8(bytes1("l"))));
        harness.validateCid(string(bad));
    }

    function test_validateCid_v1_reverts_invalid_base32_char() public {
        bytes memory bad = bytes(VALID_CIDV1);
        bad[10] = "1"; // '1' is not in base32 lowercase (only 2-7)
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase32Char.selector, uint8(bytes1("1"))));
        harness.validateCid(string(bad));
    }

    function test_validateCid_v1_reverts_uppercase() public {
        bytes memory bad = bytes(VALID_CIDV1);
        bad[10] = "A"; // uppercase not in base32 lower
        vm.expectRevert(abi.encodeWithSelector(CidUtils.InvalidBase32Char.selector, uint8(bytes1("A"))));
        harness.validateCid(string(bad));
    }

    // =====================================================================
    //  isValidCid — RETURNS FALSE FOR INVALID
    // =====================================================================

    function test_isValidCid_empty_returns_false() public view {
        assertFalse(harness.isValidCid(""));
    }

    function test_isValidCid_too_short_returns_false() public view {
        assertFalse(harness.isValidCid("QmShort"));
    }

    function test_isValidCid_bad_prefix_returns_false() public view {
        assertFalse(harness.isValidCid("XmYwAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx"));
    }

    function test_isValidCid_v0_bad_char_returns_false() public view {
        // Replace a char with '0' (invalid base58)
        assertFalse(harness.isValidCid("Qm0wAPJzv5CZsnANqdBzXsmVQ1tSQK7EfRmS2nHb3gU5Tx"));
    }

    function test_isValidCid_v1_too_short_returns_false() public view {
        // "bafy" prefix but < 59 chars total (pad to 50)
        assertFalse(harness.isValidCid("bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3o"));
    }

    // =====================================================================
    //  FUZZ: isValidCid never reverts
    // =====================================================================

    function testFuzz_isValidCid_never_reverts(string calldata cid) public view {
        // Should never revert — just return true or false
        harness.isValidCid(cid);
    }
}
