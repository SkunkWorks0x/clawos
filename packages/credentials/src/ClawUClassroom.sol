// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

// --- Interfaces for cross-contract calls ---

interface IClawURegistry {
    struct Enrollment {
        uint256 bond;
        uint8 rank;
        uint64 enrolledAt;
        bytes32 transcriptHash;
        bool active;
    }

    function enrollments(address agent) external view returns (
        uint256 bond, uint8 rank, uint64 enrolledAt, bytes32 transcriptHash, bool active
    );
    function isEnrolled(address agent) external view returns (bool);
    function issueCredential(uint64 classId, address student, uint8 score) external;
    function issueCredentialWithMetadata(uint64 classId, address student, uint8 score, string calldata metadataCid) external;
}

interface IClawUTreasury {
    function receiveProtocolFee(uint256 amount) external;
    function receiveQualityFee(uint256 amount) external;
}

contract ClawUClassroom is AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;

    // --- Roles ---
    bytes32 public constant CHANCELLOR_ROLE = keccak256("CHANCELLOR_ROLE");

    // --- Constants ---
    uint256 public constant MIN_CLASS_FEE = 10_000_000; // $10 USDC (6 decimals)
    uint256 public constant PROFESSOR_SHARE = 70;       // 70%
    uint256 public constant TREASURY_SHARE = 20;        // 20%
    uint256 public constant QUALITY_SHARE = 10;         // 10%
    uint256 public constant CLASS_COOLDOWN = 10 days;    // min gap between classes

    // --- State ---
    IERC20 public immutable usdc;
    IClawURegistry public immutable registry;
    IClawUTreasury public treasury;
    uint64 public nextClassId;

    struct Class {
        uint64 id;
        address professor;
        string ipfsMemoryCid;
        uint256 fee;
        uint8 minPassScore;
        uint32 studentCount;
        uint32 totalRating;
        uint16 ratingCount;
        uint64 createdAt;
    }

    struct Attendance {
        address student;
        uint64 classId;
        uint64 attendedAt;
        bytes32 proofHash;
        string acpJobRef;
        uint8 score;
        bool attested;
    }

    mapping(uint64 => Class) public classes;
    mapping(bytes32 => Attendance) public attendances;       // keccak256(student, classId)
    mapping(address => uint256) public professorClaimable;   // pull pattern
    mapping(address => uint64) public lastClassCreated;      // rate limit
    mapping(bytes32 => bool) public hasRated;                // keccak256(student, classId)

    // --- Events ---
    event ClassCreated(uint64 indexed classId, address indexed professor);
    event ClassAttended(uint64 indexed classId, address indexed student);
    event ProofSubmitted(uint64 indexed classId, address indexed student, bytes32 proofHash);
    event Attested(uint64 indexed classId, address indexed student, uint8 score);
    event Rated(uint64 indexed classId, address indexed student, uint8 rating);
    event FeesClaimed(address indexed professor, uint256 amount);
    event TreasuryUpdated(address indexed newTreasury);

    // --- Errors ---
    error ZeroAddress();
    error NotProfessor();
    error NotEnrolled();
    error FeeTooLow(uint256 provided, uint256 minimum);
    error ClassCooldownActive(uint64 nextAllowed);
    error ClassNotFound(uint64 classId);
    error AlreadyAttending(uint64 classId);
    error NotAttending(uint64 classId);
    error AlreadyAttested(uint64 classId);
    error ProofNotSubmitted(uint64 classId);
    error NotAttested(uint64 classId);
    error InvalidRating();
    error AlreadyRated(uint64 classId);
    error NothingToClaim();
    error TreasuryNotSet();

    constructor(address _usdc, address _registry, address _chancellor) {
        if (_usdc == address(0) || _registry == address(0) || _chancellor == address(0)) {
            revert ZeroAddress();
        }

        usdc = IERC20(_usdc);
        registry = IClawURegistry(_registry);

        _grantRole(DEFAULT_ADMIN_ROLE, _chancellor);
        _grantRole(CHANCELLOR_ROLE, _chancellor);
    }

    // --- Mutative Functions ---

    function createClass(
        string calldata ipfsCid,
        uint256 fee,
        uint8 minPassScore
    ) external nonReentrant returns (uint64) {
        // Check professor rank via Registry
        (, uint8 rank,,, bool active) = registry.enrollments(msg.sender);
        if (!active || rank < 1) revert NotProfessor();

        // Check minimum fee
        if (fee < MIN_CLASS_FEE) revert FeeTooLow(fee, MIN_CLASS_FEE);

        // Rate limit: 10-day cooldown between classes
        uint64 lastCreated = lastClassCreated[msg.sender];
        if (lastCreated > 0 && block.timestamp < lastCreated + CLASS_COOLDOWN) {
            revert ClassCooldownActive(lastCreated + uint64(CLASS_COOLDOWN));
        }

        // Effects
        uint64 classId = nextClassId++;
        classes[classId] = Class({
            id: classId,
            professor: msg.sender,
            ipfsMemoryCid: ipfsCid,
            fee: fee,
            minPassScore: minPassScore,
            studentCount: 0,
            totalRating: 0,
            ratingCount: 0,
            createdAt: uint64(block.timestamp)
        });
        lastClassCreated[msg.sender] = uint64(block.timestamp);

        emit ClassCreated(classId, msg.sender);
        return classId;
    }

    function attendClass(uint64 classId) external nonReentrant {
        // Validate student enrollment
        if (!registry.isEnrolled(msg.sender)) revert NotEnrolled();

        // Validate class exists
        Class storage c = classes[classId];
        if (c.professor == address(0)) revert ClassNotFound(classId);

        // Validate no duplicate attendance
        bytes32 key = _attendanceKey(msg.sender, classId);
        if (attendances[key].student != address(0)) revert AlreadyAttending(classId);

        // Treasury must be set for fee splits
        if (address(treasury) == address(0)) revert TreasuryNotSet();

        // Calculate fee split
        uint256 fee = c.fee;
        uint256 profShare = (fee * PROFESSOR_SHARE) / 100;
        uint256 treasuryShare = (fee * TREASURY_SHARE) / 100;
        uint256 qualityShare = fee - profShare - treasuryShare; // remainder avoids rounding dust

        // Effects
        attendances[key] = Attendance({
            student: msg.sender,
            classId: classId,
            attendedAt: uint64(block.timestamp),
            proofHash: bytes32(0),
            acpJobRef: "",
            score: 0,
            attested: false
        });
        c.studentCount++;
        professorClaimable[c.professor] += profShare;

        // Interactions: pull full fee from student
        usdc.safeTransferFrom(msg.sender, address(this), fee);

        // Push treasury + quality shares to Treasury contract
        usdc.safeIncreaseAllowance(address(treasury), treasuryShare + qualityShare);
        treasury.receiveProtocolFee(treasuryShare);
        treasury.receiveQualityFee(qualityShare);

        emit ClassAttended(classId, msg.sender);
    }

    function submitProof(
        uint64 classId,
        bytes32 proofHash,
        string calldata acpJobRef
    ) external nonReentrant {
        bytes32 key = _attendanceKey(msg.sender, classId);
        Attendance storage a = attendances[key];

        if (a.student == address(0)) revert NotAttending(classId);
        if (a.attested) revert AlreadyAttested(classId);

        a.proofHash = proofHash;
        a.acpJobRef = acpJobRef;

        emit ProofSubmitted(classId, msg.sender, proofHash);
    }

    function attestSuccess(
        uint64 classId,
        address student,
        uint8 score
    ) external nonReentrant onlyRole(CHANCELLOR_ROLE) {
        bytes32 key = _attendanceKey(student, classId);
        Attendance storage a = attendances[key];

        if (a.student == address(0)) revert NotAttending(classId);
        if (a.proofHash == bytes32(0)) revert ProofNotSubmitted(classId);
        if (a.attested) revert AlreadyAttested(classId);

        // Effects
        a.score = score;
        a.attested = true;

        // If passing score, issue credential via Registry
        Class storage c = classes[classId];
        if (score >= c.minPassScore) {
            registry.issueCredential(classId, student, score);
        }

        emit Attested(classId, student, score);
    }

    function submitRating(uint64 classId, uint8 rating) external nonReentrant {
        if (rating < 1 || rating > 5) revert InvalidRating();

        bytes32 key = _attendanceKey(msg.sender, classId);
        Attendance storage a = attendances[key];

        if (a.student == address(0)) revert NotAttending(classId);
        if (!a.attested) revert NotAttested(classId);
        if (hasRated[key]) revert AlreadyRated(classId);

        hasRated[key] = true;

        Class storage c = classes[classId];
        c.totalRating += rating;
        c.ratingCount++;

        emit Rated(classId, msg.sender, rating);
    }

    function claimFees() external nonReentrant {
        uint256 amount = professorClaimable[msg.sender];
        if (amount == 0) revert NothingToClaim();

        professorClaimable[msg.sender] = 0;
        usdc.safeTransfer(msg.sender, amount);

        emit FeesClaimed(msg.sender, amount);
    }

    // --- Admin ---

    function setTreasury(address _treasury) external onlyRole(CHANCELLOR_ROLE) {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = IClawUTreasury(_treasury);
        emit TreasuryUpdated(_treasury);
    }

    // --- View Functions ---

    function getAttendance(address student, uint64 classId) external view returns (Attendance memory) {
        return attendances[_attendanceKey(student, classId)];
    }

    function getClass(uint64 classId) external view returns (Class memory) {
        return classes[classId];
    }

    // --- Internal ---

    function _attendanceKey(address student, uint64 classId) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(student, classId));
    }
}
