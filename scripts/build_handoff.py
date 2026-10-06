#!/usr/bin/env python3
"""Xuất episodes/EXX/handoff.md: bảng shot + prompt để đối tác copy vào Dreamina.

Dùng:  python3 scripts/build_handoff.py E01 [--force]
Từ chối xuất nếu shots.csv còn LỖI/SPLIT hoặc shot AI chưa có prompt (trừ khi --force).
"""
import csv
import sys
from datetime import date
from pathlib import Path

from validate_shots import AI_TYPES, validate

ROOT = Path(__file__).resolve().parent.parent


def load_dialogue(path):
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        lines = {}
        for row in csv.DictReader(f):
            lines.setdefault(row["shot"].strip(), []).append(row)
        return lines


def md_cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip() or "—"


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    force = "--force" in argv
    if len(args) != 1:
        print(__doc__)
        return 2
    ep = args[0]
    ep_dir = ROOT / "episodes" / ep
    shots_path = ep_dir / "shots.csv"
    if not shots_path.exists():
        print(f"Không thấy {shots_path}")
        return 2

    results = validate(shots_path)
    blockers = []
    for row, errors, splits, _ in results:
        shot = row["shot"]
        blockers += [f"shot {shot}: SPLIT — {m}" for m in splits]
        blockers += [f"shot {shot}: {m}" for m in errors]
        if row["loai_shot"].strip() in AI_TYPES and not row["prompt"].strip():
            blockers.append(f"shot {shot}: chưa có prompt")
    if blockers and not force:
        print("Chưa xuất handoff — còn vấn đề:")
        print("\n".join(f"  - {b}" for b in blockers))
        print("\nSửa shots.csv rồi chạy lại (hoặc --force nếu người duyệt cho phép).")
        return 1

    dialogue = load_dialogue(ep_dir / "dialogue.csv")
    rows = [r for r, *_ in results]
    total = sum(float(r["thoi_luong_s"]) for r in rows if r["thoi_luong_s"].strip().replace(".", "", 1).isdigit())

    out = [
        f"# Handoff {ep} — tạo clip trên Dreamina",
        "",
        f"Ngày xuất: {date.today().isoformat()} · {len(rows)} shot · tổng ~{total:g}s · tỉ lệ **9:16**",
        "",
    ]
    if blockers:
        out += ["> ⚠️ Xuất bằng `--force`, còn vấn đề chưa xử lý:", *[f"> - {b}" for b in blockers], ""]
    out += [
        "## Hướng dẫn",
        "1. Mỗi shot AI: tải đúng ảnh tham chiếu (nhân vật + bối cảnh trong `assets/refs/`), dán prompt nguyên văn.",
        "2. Đặt thời lượng clip ≥ `thoi_luong_s` (voice đã chốt).",
        "3. Shot `san_pham_that`: KHÔNG tạo bằng AI — dùng ảnh/video thật trong `assets/product/`.",
        "4. QC theo `skills/qc_checklist.md`; ghi mỗi lần tạo vào `log.csv` (shot, so_lan_tao, loai_loi, chi_phi).",
        "",
        "## Bảng shot",
        "",
        "| Shot | Scene | Loại | Giây | Nhân vật | Bối cảnh | Hành động | Camera |",
        "|------|-------|------|------|----------|----------|-----------|--------|",
    ]
    for r in rows:
        out.append("| " + " | ".join(md_cell(r[c]) for c in (
            "shot", "scene", "loai_shot", "thoi_luong_s", "nhan_vat", "boi_canh", "hanh_dong", "camera")) + " |")

    out += ["", "## Prompt từng shot", ""]
    for r in rows:
        shot = r["shot"].strip()
        out.append(f"### Shot {shot} · {r['loai_shot']} · {r['thoi_luong_s'] or '?'}s")
        out.append(f"- Nhân vật: {md_cell(r['nhan_vat'])} · Bối cảnh: {md_cell(r['boi_canh'])}")
        for d in dialogue.get(shot, []):
            out.append(f"- Thoại ({d['nhan_vat']}, {d['cam_xuc']}): “{d['cau_thoai']}” — audio: {d['file_audio'] or 'chưa có'}")
        if r["loai_shot"].strip() == "san_pham_that":
            out.append("- **Dùng footage/ảnh sản phẩm thật — không tạo bằng AI.**")
        elif r["prompt"].strip():
            out += ["", "```", r["prompt"].strip(), "```"]
        out.append("")

    dest = ep_dir / "handoff.md"
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"Đã xuất {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
