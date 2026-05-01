// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {SafeERC20, IERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract ClawUTreasury is AccessControl, ReentrancyGuard {
    using SafeERC20 for IERC20;

    bytes32 public constant CHANCELLOR_ROLE = keccak256("CHANCELLOR_ROLE");

    IERC20 public immutable usdc;
    uint256 public treasuryBalance;
    uint256 public qualityFundBalance;

    // --- Events ---
    event ProtocolFeeReceived(address indexed from, uint256 amount);
    event QualityFeeReceived(address indexed from, uint256 amount);
    event QualityBonusDistributed(address[] professors, uint256[] amounts);
    event TreasuryWithdrawn(address indexed to, uint256 amount);

    // --- Errors ---
    error ZeroAddress();
    error ZeroAmount();
    error InsufficientQualityFund(uint256 available, uint256 requested);
    error InsufficientTreasury(uint256 available, uint256 requested);
    error ArrayLengthMismatch();

    constructor(address _usdc, address _chancellor) {
        if (_usdc == address(0) || _chancellor == address(0)) revert ZeroAddress();
        usdc = IERC20(_usdc);
        _grantRole(DEFAULT_ADMIN_ROLE, _chancellor);
        _grantRole(CHANCELLOR_ROLE, _chancellor);
    }

    function receiveProtocolFee(uint256 amount) external {
        if (amount == 0) revert ZeroAmount();
        treasuryBalance += amount;
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        emit ProtocolFeeReceived(msg.sender, amount);
    }

    function receiveQualityFee(uint256 amount) external {
        if (amount == 0) revert ZeroAmount();
        qualityFundBalance += amount;
        usdc.safeTransferFrom(msg.sender, address(this), amount);
        emit QualityFeeReceived(msg.sender, amount);
    }

    function distributeQualityBonus(
        address[] calldata topProfessors,
        uint256[] calldata amounts
    ) external nonReentrant onlyRole(CHANCELLOR_ROLE) {
        if (topProfessors.length != amounts.length) revert ArrayLengthMismatch();

        uint256 total;
        for (uint256 i; i < amounts.length; ++i) {
            total += amounts[i];
        }
        if (total > qualityFundBalance) {
            revert InsufficientQualityFund(qualityFundBalance, total);
        }

        qualityFundBalance -= total;

        for (uint256 i; i < topProfessors.length; ++i) {
            usdc.safeTransfer(topProfessors[i], amounts[i]);
        }

        emit QualityBonusDistributed(topProfessors, amounts);
    }

    function withdrawTreasury(uint256 amount) external nonReentrant onlyRole(CHANCELLOR_ROLE) {
        if (amount == 0) revert ZeroAmount();
        if (amount > treasuryBalance) revert InsufficientTreasury(treasuryBalance, amount);

        treasuryBalance -= amount;
        usdc.safeTransfer(msg.sender, amount);
        emit TreasuryWithdrawn(msg.sender, amount);
    }
}
