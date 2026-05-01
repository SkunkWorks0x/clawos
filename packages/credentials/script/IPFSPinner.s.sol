// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console2} from "forge-std/Script.sol";
import {ClawURegistry} from "../src/ClawURegistry.sol";
import {CidUtils} from "../src/libraries/CidUtils.sol";

/// @title IPFSPinner — Lightweight IPFS HTTP pinning via Foundry FFI
/// @notice Pins credential metadata JSON to IPFS (via Pinata, Infura, or local node)
///         then calls issueCredentialWithMetadata on the Registry.
/// @dev Requires IPFS_API_URL and IPFS_API_KEY env vars.
///      Uses `curl` via FFI — no full IPFS node needed.
contract IPFSPinner is Script {
    /// @notice Pins JSON to IPFS via HTTP API and returns the CID.
    /// @param jsonPayload The metadata JSON string to pin.
    /// @return cid The IPFS CID returned by the pinning service.
    function pinToIPFS(string memory jsonPayload) public returns (string memory cid) {
        string memory apiUrl = vm.envString("IPFS_API_URL");
        string memory apiKey = vm.envString("IPFS_API_KEY");

        // Build curl command for Pinata-compatible API
        string[] memory cmd = new string[](10);
        cmd[0] = "curl";
        cmd[1] = "-s";
        cmd[2] = "-X";
        cmd[3] = "POST";
        cmd[4] = string.concat(apiUrl, "/pinning/pinJSONToIPFS");
        cmd[5] = "-H";
        cmd[6] = string.concat("Authorization: Bearer ", apiKey);
        cmd[7] = "-H";
        cmd[8] = "Content-Type: application/json";
        cmd[9] = string.concat('{"pinataContent":', jsonPayload, "}");

        bytes memory result = vm.ffi(cmd);
        // Parse CID from JSON response: {"IpfsHash":"Qm...","PinSize":...,"Timestamp":"..."}
        cid = _extractIpfsHash(string(result));
    }

    /// @notice Builds credential metadata JSON for a student credential.
    function buildMetadataJson(
        address student,
        uint64 classId,
        uint8 score,
        string memory className,
        string memory professorName
    ) public pure returns (string memory) {
        return string.concat(
            '{"student":"',
            vm.toString(student),
            '","classId":',
            vm.toString(classId),
            ',"score":',
            vm.toString(score),
            ',"className":"',
            _escapeJsonString(className),
            '","professor":"',
            _escapeJsonString(professorName),
            '","protocol":"ClawU","version":"1.0"}'
        );
    }

    /// @dev Escapes characters that would break JSON string values.
    function _escapeJsonString(string memory s) internal pure returns (string memory) {
        bytes memory b = bytes(s);
        // Count chars that need escaping to size the output buffer
        uint256 extra;
        for (uint256 i; i < b.length; ++i) {
            if (b[i] == '"' || b[i] == "\\") ++extra;
        }
        if (extra == 0) return s;

        bytes memory escaped = new bytes(b.length + extra);
        uint256 j;
        for (uint256 i; i < b.length; ++i) {
            if (b[i] == '"' || b[i] == "\\") {
                escaped[j++] = "\\";
            }
            escaped[j++] = b[i];
        }
        return string(escaped);
    }

    /// @notice Full workflow: build metadata, pin to IPFS, issue credential on-chain.
    function pinAndIssue(
        address registryAddr,
        uint64 classId,
        address student,
        uint8 score,
        string memory className,
        string memory professorName
    ) public {
        string memory json = buildMetadataJson(student, classId, score, className, professorName);

        console2.log("Pinning metadata to IPFS...");
        string memory cid = pinToIPFS(json);
        console2.log("Pinned CID:", cid);

        ClawURegistry registry = ClawURegistry(registryAddr);

        vm.broadcast();
        registry.issueCredentialWithMetadata(classId, student, score, cid);
        console2.log("Credential issued with metadata CID");
    }

    /// @dev Extracts the IpfsHash value from a Pinata-style JSON response.
    ///      Naive parser — finds "IpfsHash":"<value>" and returns <value>.
    function _extractIpfsHash(string memory json) internal pure returns (string memory) {
        bytes memory b = bytes(json);
        bytes memory needle = bytes('"IpfsHash":"');
        uint256 needleLen = needle.length;

        for (uint256 i; i + needleLen < b.length; ++i) {
            bool found = true;
            for (uint256 j; j < needleLen; ++j) {
                if (b[i + j] != needle[j]) {
                    found = false;
                    break;
                }
            }
            if (found) {
                uint256 start = i + needleLen;
                uint256 end = start;
                while (end < b.length && b[end] != '"') {
                    ++end;
                }
                bytes memory cidBytes = new bytes(end - start);
                for (uint256 k; k < end - start; ++k) {
                    cidBytes[k] = b[start + k];
                }
                return string(cidBytes);
            }
        }
        revert("IPFSPinner: IpfsHash not found in response");
    }
}
