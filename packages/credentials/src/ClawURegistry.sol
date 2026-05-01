// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Initializable} from "@openzeppelin/contracts-upgradeable/proxy/utils/Initializable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";
import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {ReentrancyGuardUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {CidUtils} from "./libraries/CidUtils.sol";

contract ClawURegistry is
    Initializable,
    UUPSUpgradeable,
    AccessControlUpgradeable,
    ReentrancyGuardUpgradeable
{
    using SafeERC20 for IERC20;

    // --- Roles ---
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    bytes32 public constant CHANCELLOR_ROLE = keccak256("CHANCELLOR_ROLE");

    // --- Constants ---
    uint256 public constant MIN_BOND = 10_000_000; // $10 USDC (6 decimals)

    // --- State ---
    IERC20 public usdc;
    address public treasury; // receives slashed bonds

    struct Enrollment {
        uint256 bond;
        uint8 rank;             // 0=student, 1=professor
        uint64 enrolledAt;
        bytes32 transcriptHash;
        bool active;
    }

    struct Credential {
        address owner;
        uint64 classId;
        uint8 score;            // 0-100
        uint64 issuedAt;
        string metadataCid;     // IPFS CID of credential metadata JSON
    }

    mapping(address => Enrollment) public enrollments;
    mapping(bytes32 => Credential) public credentials; // keccak256(agent, classId)

    // --- Storage gap for upgrades ---
    uint256[50] private __gap;

    // --- Events ---
    event Enrolled(address indexed agent, uint256 bondAmount);
    event CredentialIssued(address indexed student, uint64 indexed classId, uint8 score, string metadataCid);
    event BondSlashed(address indexed agent, uint256 amount);
    event Promoted(address indexed agent, uint8 newRank);
    event TreasuryUpdated(address indexed newTreasury);

    // --- Errors ---
    error BondTooLow(uint256 provided, uint256 minimum);
    error AlreadyEnrolled();
    error NotEnrolled();
    error InsufficientBond(uint256 available, uint256 requested);
    error ZeroAddress();

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(address _usdc, address _chancellor) public initializer {
        if (_usdc == address(0) || _chancellor == address(0)) revert ZeroAddress();

        __UUPSUpgradeable_init();
        __AccessControl_init();
        __ReentrancyGuard_init();

        usdc = IERC20(_usdc);

        _grantRole(DEFAULT_ADMIN_ROLE, _chancellor);
        _grantRole(UPGRADER_ROLE, _chancellor);
        _grantRole(CHANCELLOR_ROLE, _chancellor);
    }

    // --- External Functions ---

    function enroll(uint256 bondAmount, string calldata acpJobRef) external nonReentrant {
        if (bondAmount < MIN_BOND) revert BondTooLow(bondAmount, MIN_BOND);
        if (enrollments[msg.sender].active) revert AlreadyEnrolled();

        // Effects
        enrollments[msg.sender] = Enrollment({
            bond: bondAmount,
            rank: 0,
            enrolledAt: uint64(block.timestamp),
            transcriptHash: bytes32(0),
            active: true
        });

        // Interactions
        usdc.safeTransferFrom(msg.sender, address(this), bondAmount);

        emit Enrolled(msg.sender, bondAmount);
    }

    function issueCredential(
        uint64 classId,
        address student,
        uint8 score
    ) external onlyRole(CHANCELLOR_ROLE) {
        _issueCredential(classId, student, score, "");
    }

    function issueCredentialWithMetadata(
        uint64 classId,
        address student,
        uint8 score,
        string calldata metadataCid
    ) external onlyRole(CHANCELLOR_ROLE) {
        CidUtils.validateCid(metadataCid);
        _issueCredential(classId, student, score, metadataCid);
    }

    function _issueCredential(
        uint64 classId,
        address student,
        uint8 score,
        string memory metadataCid
    ) internal {
        if (!enrollments[student].active) revert NotEnrolled();

        bytes32 key = keccak256(abi.encodePacked(student, classId));
        credentials[key] = Credential({
            owner: student,
            classId: classId,
            score: score,
            issuedAt: uint64(block.timestamp),
            metadataCid: metadataCid
        });

        // Update rolling transcript hash
        enrollments[student].transcriptHash = keccak256(
            abi.encodePacked(enrollments[student].transcriptHash, classId, score)
        );

        emit CredentialIssued(student, classId, score, metadataCid);
    }

    function slashBond(address agent, uint256 amount) external nonReentrant onlyRole(CHANCELLOR_ROLE) {
        Enrollment storage e = enrollments[agent];
        if (!e.active) revert NotEnrolled();
        if (e.bond < amount) revert InsufficientBond(e.bond, amount);

        // Effects
        e.bond -= amount;
        if (e.bond == 0) {
            e.active = false;
        }

        // Interactions — send slashed USDC to treasury (or chancellor if treasury not set)
        address recipient = treasury != address(0) ? treasury : msg.sender;
        usdc.safeTransfer(recipient, amount);

        emit BondSlashed(agent, amount);
    }

    function promote(address agent, uint8 newRank) external onlyRole(CHANCELLOR_ROLE) {
        if (!enrollments[agent].active) revert NotEnrolled();
        enrollments[agent].rank = newRank;
        emit Promoted(agent, newRank);
    }

    function setTreasury(address _treasury) external onlyRole(CHANCELLOR_ROLE) {
        treasury = _treasury;
        emit TreasuryUpdated(_treasury);
    }

    // --- View Functions ---

    function getCredential(address agent, uint64 classId) external view returns (Credential memory) {
        return credentials[keccak256(abi.encodePacked(agent, classId))];
    }

    function isEnrolled(address agent) external view returns (bool) {
        return enrollments[agent].active;
    }

    // --- UUPS ---

    function _authorizeUpgrade(address) internal override onlyRole(UPGRADER_ROLE) {}
}
