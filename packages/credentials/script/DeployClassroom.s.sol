// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Script, console2} from "forge-std/Script.sol";
import {ClawURegistry} from "../src/ClawURegistry.sol";
import {ClawUClassroom} from "../src/ClawUClassroom.sol";
import {ClawUTreasury} from "../src/ClawUTreasury.sol";
import {MockUSDC} from "../test/mocks/MockUSDC.sol";

contract DeployClassroom is Script {
    // Existing Base Sepolia deployments
    address constant REGISTRY_PROXY = 0xA647d92209F6015c9934714dFe0756c931571BBe;
    address constant MOCK_USDC = 0x5731D0B398827F8320190fA3bdacFa6527f4568f;

    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        uint256 studentKey = vm.envUint("STUDENT_PRIVATE_KEY");
        address deployer = vm.addr(deployerKey);
        address student = vm.addr(studentKey);

        ClawURegistry registry = ClawURegistry(REGISTRY_PROXY);
        MockUSDC usdc = MockUSDC(MOCK_USDC);

        console2.log("=== DEPLOYING ===");
        console2.log("Deployer (chancellor/professor):", deployer);
        console2.log("Student:", student);

        // ============================================================
        //  PHASE 1: Deploy Treasury + Classroom (as deployer)
        // ============================================================
        vm.startBroadcast(deployerKey);

        // 1. Deploy Treasury
        ClawUTreasury treasury = new ClawUTreasury(MOCK_USDC, deployer);
        console2.log("Treasury:", address(treasury));

        // 2. Deploy Classroom
        ClawUClassroom classroom = new ClawUClassroom(MOCK_USDC, REGISTRY_PROXY, deployer);
        console2.log("Classroom:", address(classroom));

        // 3. Wire: set treasury on Classroom
        classroom.setTreasury(address(treasury));
        console2.log("Classroom treasury set");

        // 4. Wire: set treasury on Registry (for slashed bonds)
        registry.setTreasury(address(treasury));
        console2.log("Registry treasury set");

        // 5. Grant Classroom the CHANCELLOR_ROLE on Registry
        //    (so attestSuccess -> issueCredential works)
        bytes32 chancellorRole = registry.CHANCELLOR_ROLE();
        registry.grantRole(chancellorRole, address(classroom));
        console2.log("Classroom granted CHANCELLOR_ROLE on Registry");

        // ============================================================
        //  PHASE 2: Promote deployer to professor
        // ============================================================
        // Deployer is already enrolled from previous session
        registry.promote(deployer, 1); // rank 1 = professor
        console2.log("Deployer promoted to professor (rank 1)");

        // ============================================================
        //  PHASE 3: Create test class
        // ============================================================
        uint64 classId = classroom.createClass("QmTestClass001", 10_000_000, 60);
        console2.log("Class created, ID:", classId);

        // ============================================================
        //  PHASE 4: Fund student wallet
        // ============================================================
        // Mint USDC to student
        usdc.mint(student, 100_000_000); // 100 USDC
        console2.log("Minted 100 USDC to student");

        // Send student some ETH for gas
        (bool sent,) = student.call{value: 0.00003 ether}("");
        require(sent, "ETH transfer failed");
        console2.log("Sent 0.00003 ETH to student for gas");

        vm.stopBroadcast();

        // ============================================================
        //  PHASE 5: Student enrolls + attends (as student)
        // ============================================================
        vm.startBroadcast(studentKey);

        // Approve Registry for enrollment bond
        usdc.approve(REGISTRY_PROXY, type(uint256).max);
        // Approve Classroom for class fee
        usdc.approve(address(classroom), type(uint256).max);

        // Enroll
        registry.enroll(10_000_000, "test-acp-student-001"); // $10 bond
        console2.log("Student enrolled with $10 bond");

        // Attend class
        classroom.attendClass(classId);
        console2.log("Student attended class", classId);

        vm.stopBroadcast();

        // ============================================================
        //  PHASE 6: Log expected fee split
        // ============================================================
        console2.log("=== FEE SPLIT VERIFICATION ===");
        console2.log("Professor claimable (70%):", classroom.professorClaimable(deployer));
        console2.log("Treasury balance (20%):", treasury.treasuryBalance());
        console2.log("Quality fund (10%):", treasury.qualityFundBalance());
        console2.log("Classroom USDC bal:", usdc.balanceOf(address(classroom)));
        console2.log("Treasury USDC bal:", usdc.balanceOf(address(treasury)));
        console2.log("Student USDC bal:", usdc.balanceOf(student));
    }
}
