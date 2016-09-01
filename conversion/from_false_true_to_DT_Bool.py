def from_false_true_to_DT_Bool(x):
    # false - true translated to 0 - 1
    if str(x) == "False":
        return 0
    else:
        return 1
