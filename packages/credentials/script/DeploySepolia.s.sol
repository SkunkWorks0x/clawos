// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console2} from "forge-std/Script.sol";
import {ClawURegistry} from "../src/ClawURegistry.sol";
import {MockUSDC} from "../test/mocks/MockUSDC.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

/// @notice Deploys MockUSDC + ClawURegistry (UUPS proxy) to Base Sepolia
contract DeploySepolia is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);

        console2.log("Deployer:", deployer);

        vm.startBroadcast(deployerKey);

        // 1. Deploy MockUSDC (no real USDC on Sepolia)
        MockUSDC usdc = new MockUSDC();
        console2.log("MockUSDC:", address(usdc));

        // 2. Deploy ClawURegistry implementation
        ClawURegistry registryImpl = new ClawURegistry();
        console2.log("Registry impl:", address(registryImpl));

        // 3. Deploy ERC1967Proxy with initialization
        bytes memory initData = abi.encodeCall(
            ClawURegistry.initialize,
            (address(usdc), deployer) // deployer = chancellor
        );
        ERC1967Proxy registryProxy = new ERC1967Proxy(
            address(registryImpl),
            initData
        );
        console2.log("Registry proxy:", address(registryProxy));

        // 4. Mint test USDC to deployer for testing
        usdc.mint(deployer, 10_000e6); // $10,000 test USDC
        console2.log("Minted 10,000 USDC to deployer");

        vm.stopBroadcast();
    }
}
