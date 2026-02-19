from parse_pdf import parse_time_to_seconds


def test_parse_time_to_seconds():
    cases = {
        '1:06.28': 66.28,
        '1:09.195': 69.195,
        '0:23.2': 23.2,
        '66.28': 66.28,
        '23.2': 23.2,
        'DQ': None,
        '': None,
        None: None,
        '2:00': 120.0,
        '3:00.500': 180.5,
    }

    failed = []
    for s, expected in cases.items():
        got = parse_time_to_seconds(s)
        if got is None and expected is None:
            continue
        if got is None and expected is not None:
            failed.append((s, expected, got))
        elif abs(got - expected) > 1e-6:
            failed.append((s, expected, got))

    if failed:
        for s, exp, g in failed:
            print(f"FAIL: '{s}' expected {exp} got {g}")
        raise SystemExit(1)
    print("All parse_time_to_seconds tests passed")


if __name__ == '__main__':
    test_parse_time_to_seconds()
