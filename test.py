class Solution:
    def search(self, nums: list[int], target: int) -> int:
        # find the offset: find the max value
        # check i and j
        # if i < j, eliminate lower half
        # if j > i, eliminate upper half

        i, j = 0, len(nums) - 1
        zero_val = nums[0]

        while i < j:
            idx = (j + i) // 2
            if nums[idx] < zero_val:
                j = idx
            else:
                i = idx + 1

        offset = i - 1

        return offset


print(Solution().search([4, 5, 6, 7, 0, 1, 2], 1))
