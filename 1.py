

def merge2Arrs(arr1, arr2):
    # arr1, arr2: sorted arrays
    l1 = len(arr1)
    l2 = len(arr2)
    arr = []
    point1 = 0
    point2 = 0
    while point1 < min(l1, l2) or point2 < min(l1, l2):
        if arr1[point1] < arr2[point2]:
            arr.append(arr1[point1])
            point1 += 1
        else:
            arr.append(arr2[point2])
            point2 += 1

    if point1 < l1:
        arr.extend(arr1[point1:l1])
    if point2 < l2:
        arr.extend(arr2[point2:l2])
    return arr

arr1 = [1, 4, 7]
arr2 = [2, 3, 5, 6, 8]
arr = merge2Arrs(arr1, arr2)
print(f"{arr1} merged with {arr2} get {arr}")
