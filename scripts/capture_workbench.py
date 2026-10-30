"""用真实浏览器操作工作台，保存可直接用于成果汇报的页面截图。"""
import argparse
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:8765")
    args=parser.parse_args()
    output=ROOT/"artifacts/screenshots"
    output.mkdir(parents=True,exist_ok=True)
    with urlopen(args.url+"/api/runs") as response:
        runs=json.load(response)["items"]
    full=sorted([r for r in runs if r["id"].endswith("_full_selected")],key=lambda r:r["strategy"]!="low_vol_momentum")
    validation=sorted([r for r in runs if r["id"].endswith("_validation_selected")],key=lambda r:r["strategy"]!="low_vol_momentum")
    evidence={"browser_errors":[],"screenshots":[],"views":[]}
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(channel="chrome",headless=True)
        page=browser.new_page(viewport={"width":1600,"height":1100},device_scale_factor=1)
        page.on("pageerror",lambda exc:evidence["browser_errors"].append(str(exc)))
        page.goto(args.url,wait_until="networkidle")
        page.locator("#run-select").wait_for(timeout=7000)
        def capture(name):
            page.screenshot(path=str(output/name),full_page=False)
            evidence["screenshots"].append(name)
        for row in full:
            page.locator("#run-select").select_option(row["id"])
            page.locator("#nav-chart svg path").first.wait_for(timeout=7000)
            page.wait_for_timeout(300)
            capture(row["strategy"]+"_full.png")
        for rows,name in [(full,"comparison_full.png"),(validation,"comparison_validation.png")]:
            page.goto(args.url+"/?capture="+name+"#runs",wait_until="networkidle")
            page.locator('[data-compare]').first.wait_for(timeout=7000)
            for row in rows:
                page.locator(f'[data-compare="{row["id"]}"]').click()
            page.locator('[data-action="compare"]').click()
            page.wait_for_function("document.querySelectorAll('#nav-chart svg path').length === 3",timeout=7000)
            page.wait_for_timeout(300)
            evidence[name]=page.locator("#legend").inner_text()
            capture(name)
        for view in ["factors","data"]:
            page.locator(f'[data-view="{view}"]').first.click()
            page.wait_for_timeout(700)
            capture(view+".png")
            evidence["views"].append(view)
        page.locator('[data-action="new"]').first.click() if page.locator('[data-action="new"]').count() else page.locator('[data-view="overview"]').first.click()
        if not page.locator("#run-form").count():
            page.locator('[data-action="new"]').click()
        page.locator("#f-name").fill("界面提交 · 低波动动量 · 2026年9月")
        page.locator("#f-strategy").select_option("low_vol_momentum")
        page.locator("#f-start").fill("2026-09-01")
        page.locator("#f-end").fill("2026-09-30")
        page.locator("#submit-run").click()
        page.wait_for_timeout(500)
        capture("job_submission.png")
        evidence["ui_submission"]=True
        page.locator('[data-view="overview"]').first.click()
        page.wait_for_timeout(500)
        with page.expect_download() as download:
            page.locator('a[href$="/download/equity.csv"]').click()
        evidence["download"]=download.value.suggested_filename
        page.set_viewport_size({"width":390,"height":844})
        page.wait_for_timeout(5500)
        capture("mobile.png")
        evidence["mobile_horizontal_overflow"]=page.evaluate("document.documentElement.scrollWidth > innerWidth")
        browser.close()
    (ROOT/"artifacts/browser_acceptance.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(evidence,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
