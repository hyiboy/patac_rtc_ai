import re
import json
from pathlib import Path

# ========== 正则 ==========
PROPERTY_LINE_RE = re.compile(
    r'\{\s*\(int32_t\)\s*(\w+)::(\w+)\s*,\s*Signal::(\w+)\s*,\s*Signal::(\w+)\s*\}'
)

PROP_ID_RE = re.compile(
    r'\{\s*(\d+)\s*,\s*"(\w+)::(\w+)"\s*\}'
)

SIGNAL_BLOCK_RE = re.compile(
    r'\{\s*\.name\s*=\s*"(\w+)".*?\.upper\s*=\s*(-?\d+).*?\.lower\s*=\s*(-?\d+).*?\.validityBit\s*=\s*(-?\d+).*?\.dudBit\s*=\s*(-?\d+)',
    re.S
)

# ========== 解析函数 ==========
def parse_property_signal_file(path: Path):
    results = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("//"):
            continue

        m = PROPERTY_LINE_RE.search(line)
        if not m:
            continue

        field, prop, sig2, sig3 = m.groups()

        if sig2 == "INVALID":
            access = "WRITE"
            signal = sig3
        elif sig3 == "INVALID":
            access = "READ"
            signal = sig2
        else:
            access = "READ_WRITE"
            signal = sig2

        results.append({
            "field": field,
            "propertyName": prop,
            "signal": signal,
            "access": access
        })
    return results


def parse_property_id_file(path: Path):
    mapping = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = PROP_ID_RE.search(line)
        if m:
            prop_id, field, name = m.groups()
            mapping[(field, name)] = prop_id
    return mapping


def parse_signal_info_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")

    # 找每一个 { ... } block
    blocks = re.findall(r'\{(.*?)\},', text, re.S)
    info = {}

    for block in blocks:
        def find(field):
            m = re.search(rf'\.{field}\s*=\s*([-\w\."]+)', block)
            if not m:
                return ""
            val = m.group(1).strip()
            return val.strip('"')

        name = find("name")
        if not name:
            continue

        entry = {
            "maxValue": find("upper"),
            "minValue": find("lower"),
            "validPos": find("validityBit"),
            "dudPos": find("dudBit"),
            "scale": find("scale"),
            "offset": find("offset"),
        }

        info[name] = entry

    return info


# ========== 主流程 ==========
def build_property_json(
    prop_sig_path,
    prop_id_path,
    signal_info_path,
    output_json
):
    prop_sig = parse_property_signal_file(Path(prop_sig_path))
    prop_ids = parse_property_id_file(Path(prop_id_path))
    signal_info = parse_signal_info_file(Path(signal_info_path))

    result = []

    for item in prop_sig:
        key = (item["field"], item["propertyName"])
        if key not in prop_ids:
            continue

        entry = {
            "propertyName": item["propertyName"],
            "propertyID": prop_ids[key],
            "field": item["field"],
            "signal": item["signal"],
            "access": item["access"],
            "scale": "1",
            "offset": "0",
            "maxValue": "",
            "minValue": "",
            "validPos": "",
            "dudPos": "",
        }

        if item["signal"] in signal_info:
            entry.update(signal_info[item["signal"]])

        result.append(entry)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"生成完成，共 {len(result)} 条 → {output_json}")

if __name__ == "__main__":
    build_property_json(
        prop_sig_path=r"\\sghkvm0005.apac.bosch.com\home_cse3wx\files\backup\qcom_la\lagvm\LINUX\android\vendor\gm\hardware\impls\vehicle\impl\arxml\gem\SimplePropertyInfo.cpp",
        prop_id_path=r"\\sghkvm0005.apac.bosch.com\home_cse3wx\files\backup\qcom_la\lagvm\LINUX\android\vendor\gm\hardware\impls\vehicle\impl\log\PatacLogInfo.cpp",
        signal_info_path=r"\\sghkvm0005.apac.bosch.com\home_cse3wx\files\backup\qcom_la\lagvm\LINUX\android\vendor\gm\hardware\impls\vehicle\impl\arxml\gem\SignalInfo.cpp",
        output_json=r"property_signal_db.json"
    )
