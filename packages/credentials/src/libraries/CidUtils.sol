// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

/// @title CidUtils — IPFS CID validation for ClawU credentials
/// @notice Validates CIDv0 (Qm...) and CIDv1 (bafy...) format strings on-chain.
library CidUtils {
    error EmptyCid();
    error CidTooShort();
    error CidTooLong();
    error InvalidCidPrefix();
    error InvalidBase58Char(uint8 char);
    error InvalidBase32Char(uint8 char);

    uint256 internal constant CIDV0_LENGTH = 46;       // Qm + 44 base58 chars
    uint256 internal constant CIDV1_MIN_LENGTH = 59;   // bafybeig... (typical)
    uint256 internal constant CID_MAX_LENGTH = 128;    // generous upper bound

    /// @notice Validates that a CID string has a valid IPFS format.
    /// @dev Checks prefix (Qm for v0, bafy for v1) and character set.
    function validateCid(string calldata cid) internal pure {
        bytes memory b = bytes(cid);

        if (b.length == 0) revert EmptyCid();
        if (b.length < CIDV0_LENGTH) revert CidTooShort();
        if (b.length > CID_MAX_LENGTH) revert CidTooLong();

        if (b[0] == "Q" && b[1] == "m") {
            if (b.length != CIDV0_LENGTH) revert CidTooShort();
            _validateCidV0(b);
        } else if (
            b[0] == "b" && b[1] == "a" && b[2] == "f" && b[3] == "y"
        ) {
            if (b.length < CIDV1_MIN_LENGTH) revert CidTooShort();
            _validateCidV1(b);
        } else {
            revert InvalidCidPrefix();
        }
    }

    /// @notice Checks if a CID string is non-empty and structurally valid.
    /// @return True if the CID passes validation, false otherwise.
    function isValidCid(string calldata cid) internal pure returns (bool) {
        bytes memory b = bytes(cid);

        if (b.length < CIDV0_LENGTH || b.length > CID_MAX_LENGTH) return false;

        if (b[0] == "Q" && b[1] == "m") {
            return _isValidBase58(b);
        } else if (
            b.length >= CIDV1_MIN_LENGTH
                && b[0] == "b" && b[1] == "a" && b[2] == "f" && b[3] == "y"
        ) {
            return _isValidBase32Lower(b);
        }

        return false;
    }

    // --- Internal ---

    function _validateCidV0(bytes memory b) private pure {
        for (uint256 i; i < b.length; ++i) {
            if (!_isBase58Char(uint8(b[i]))) {
                revert InvalidBase58Char(uint8(b[i]));
            }
        }
    }

    function _validateCidV1(bytes memory b) private pure {
        for (uint256 i; i < b.length; ++i) {
            if (!_isBase32LowerChar(uint8(b[i]))) {
                revert InvalidBase32Char(uint8(b[i]));
            }
        }
    }

    function _isValidBase58(bytes memory b) private pure returns (bool) {
        if (b.length != CIDV0_LENGTH) return false;
        for (uint256 i; i < b.length; ++i) {
            if (!_isBase58Char(uint8(b[i]))) return false;
        }
        return true;
    }

    function _isValidBase32Lower(bytes memory b) private pure returns (bool) {
        for (uint256 i; i < b.length; ++i) {
            if (!_isBase32LowerChar(uint8(b[i]))) return false;
        }
        return true;
    }

    /// @dev Base58 alphabet: 123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
    ///      Excludes: 0, I, O, l
    function _isBase58Char(uint8 c) private pure returns (bool) {
        // 0-9 (0x30-0x39) excluding '0' (0x30)
        if (c >= 0x31 && c <= 0x39) return true;
        // A-Z (0x41-0x5A) excluding I (0x49) and O (0x4F)
        if (c >= 0x41 && c <= 0x5A && c != 0x49 && c != 0x4F) return true;
        // a-z (0x61-0x7A) excluding l (0x6C)
        if (c >= 0x61 && c <= 0x7A && c != 0x6C) return true;
        return false;
    }

    /// @dev Base32 lowercase: a-z, 2-7
    function _isBase32LowerChar(uint8 c) private pure returns (bool) {
        if (c >= 0x61 && c <= 0x7A) return true; // a-z
        if (c >= 0x32 && c <= 0x37) return true; // 2-7
        return false;
    }
}
