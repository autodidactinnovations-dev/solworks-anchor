// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract SolWorksAnchor {
    address public immutable owner;
    uint256 public anchorCount;
    mapping(bytes32 => uint256) public anchoredAt; // root => timestamp

    event Anchored(uint256 indexed anchorId, bytes32 indexed root, uint256 entryCount, uint256 timestamp);

    constructor() { owner = msg.sender; }

    function anchor(bytes32 root, uint256 entryCount) external {
        require(msg.sender == owner, "not owner");
        require(anchoredAt[root] == 0, "already anchored");
        anchoredAt[root] = block.timestamp;
        emit Anchored(anchorCount++, root, entryCount, block.timestamp);
    }
}
