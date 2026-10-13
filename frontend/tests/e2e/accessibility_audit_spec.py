from __future__ import annotations

import json
import unittest

from playwright.sync_api import expect, sync_playwright

from frontend.tests.e2e.player_basic_spec import PlayerBasicBrowserTests


ACCESSIBILITY_AUDIT = {
    "required_landmarks": ["banner", "main", "navigation"],
    "checks": [
        "interactive controls have accessible names",
        "images have alternative text",
        "ARIA ID references resolve",
        "text contrast meets WCAG AA",
        "visible keyboard focus is distinguishable",
        "reduced-motion preferences are honored",
    ],
}


class AccessibilityAuditBrowserTests(PlayerBasicBrowserTests):
    test_media_player_loads_plays_buffers_and_releases_previous_source = None

    def test_accessibility_audit_on_discovery_and_keyboard_suggestions(self) -> None:
        results = {
            "items": [
                {
                    "id": "one",
                    "title": "Sample item",
                    "duration": 12,
                    "thumbnailUrl": None,
                    "creator": {"id": "creator", "username": "sample"},
                    "tags": ["sample"],
                }
            ],
            "page": 1,
            "limit": 20,
            "hasMore": False,
            "total": 1,
        }

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.route(
                    "**/api/search?*",
                    lambda route: route.fulfill(
                        content_type="application/json", body=json.dumps(results)
                    ),
                )
                page.route(
                    "**/api/tags/suggest?*",
                    lambda route: route.fulfill(
                        content_type="application/json", body='["sample"]'
                    ),
                )
                page.goto(
                    f"http://127.0.0.1:{self.web_port}/", wait_until="networkidle"
                )
                page.get_by_test_id("search-submit").click()
                expect(page.get_by_test_id("result-card")).to_have_count(1)
                page.get_by_test_id("search-query").fill("#sa")
                expect(page.get_by_test_id("tag-suggestion")).to_be_visible()

                audit = page.evaluate(
                    """() => {
                      const visible = element =>
                        element.getClientRects().length > 0 &&
                        getComputedStyle(element).visibility !== "hidden";
                      const controls = [
                        ...document.querySelectorAll(
                          "button, input, select, textarea, a[href], [role='button'], [role='option']"
                        ),
                      ].filter(visible);
                      const unnamedControls = controls
                        .filter(element => {
                          const name = element.getAttribute("aria-label") ||
                            element.getAttribute("aria-labelledby") ||
                            element.labels?.length && [...element.labels]
                              .map(label => label.innerText).join(" ") ||
                            element.innerText ||
                            element.getAttribute("title") ||
                            element.getAttribute("placeholder");
                          return !name?.trim();
                        })
                        .map(element => element.outerHTML);
                      const missingAlt = [...document.images]
                        .filter(image => !image.hasAttribute("alt"))
                        .map(image => image.outerHTML);
                      const brokenReferences = [
                        ...document.querySelectorAll(
                          "[aria-controls], [aria-describedby], [aria-labelledby], [aria-activedescendant]"
                        ),
                      ].flatMap(element =>
                        ["aria-controls", "aria-describedby", "aria-labelledby",
                          "aria-activedescendant"]
                          .flatMap(attribute => (element.getAttribute(attribute) || "")
                            .split(/\\s+/)
                            .filter(Boolean)
                            .filter(id => !document.getElementById(id))
                            .map(id => `${attribute}=${id}`))
                      );
                      const channels = color =>
                        (color.match(/[\\d.]+/g) || []).map(Number);
                      const composite = (foreground, background) => {
                        const alpha = foreground[3] + background[3] *
                          (1 - foreground[3]);
                        return [
                          0, 1, 2,
                        ].map(channel => alpha === 0 ? 0 :
                          (foreground[channel] * foreground[3] +
                            background[channel] * background[3] *
                            (1 - foreground[3])) / alpha).concat(alpha);
                      };
                      const backgroundFor = element => {
                        const layers = [];
                        for (let node = element; node; node = node.parentElement) {
                          const values = channels(
                            getComputedStyle(node).backgroundColor
                          );
                          if (values.length >= 3) {
                            layers.push([...values.slice(0, 3),
                              values.length > 3 ? values[3] : 1]);
                          }
                        }
                        return layers.reverse().reduce(
                          (background, layer) =>
                            composite(layer, background),
                          [255, 255, 255, 1],
                        );
                      };
                      const luminance = color => color.slice(0, 3)
                        .map(channel => channel / 255)
                        .map(channel => channel <= 0.04045
                          ? channel / 12.92
                          : ((channel + 0.055) / 1.055) ** 2.4)
                        .reduce((sum, channel, index) =>
                          sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
                      const contrastFailures = [
                        ...document.querySelectorAll(
                          "h1, h2, h3, p, label, button, a, [role='status']"
                        ),
                      ].filter(element => visible(element) &&
                        element.innerText?.trim())
                        .flatMap(element => {
                          const style = getComputedStyle(element);
                          const foreground = channels(style.color);
                          const textColor = [...foreground.slice(0, 3),
                            foreground.length > 3 ? foreground[3] : 1];
                          const background = backgroundFor(element);
                          const rendered = composite(textColor, background);
                          const ratio = (Math.max(
                            luminance(rendered), luminance(background)
                          ) + 0.05) /
                            (Math.min(luminance(rendered),
                              luminance(background)) + 0.05);
                          const fontSize = parseFloat(style.fontSize);
                          const large = fontSize >= 24 ||
                            (parseInt(style.fontWeight, 10) >= 700 &&
                              fontSize >= 18.66);
                          return ratio < (large ? 3 : 4.5)
                            ? [`${element.tagName}: ${element.innerText.trim()} (${ratio.toFixed(2)}:1)`]
                            : [];
                        });
                      return {
                        landmarks: {
                          banner: document.querySelectorAll("header").length,
                          main: document.querySelectorAll("main").length,
                          navigation: document.querySelectorAll("nav").length,
                        },
                        headingCount: document.querySelectorAll("h1").length,
                        unnamedControls,
                        missingAlt,
                        brokenReferences,
                        contrastFailures,
                      };
                    }"""
                )
                for landmark in ACCESSIBILITY_AUDIT["required_landmarks"]:
                    count = audit["landmarks"][landmark]
                    self.assertGreaterEqual(count, 1, f"{landmark}: {audit}")
                self.assertEqual(audit["landmarks"]["banner"], 1, audit)
                self.assertEqual(audit["landmarks"]["main"], 1, audit)
                self.assertEqual(audit["headingCount"], 1, audit)
                self.assertEqual(
                    audit["unnamedControls"],
                    [],
                    f"{ACCESSIBILITY_AUDIT['checks'][0]}: {audit}",
                )
                self.assertEqual(
                    audit["missingAlt"],
                    [],
                    f"{ACCESSIBILITY_AUDIT['checks'][1]}: {audit}",
                )
                self.assertEqual(
                    audit["brokenReferences"],
                    [],
                    f"{ACCESSIBILITY_AUDIT['checks'][2]}: {audit}",
                )
                self.assertEqual(
                    audit["contrastFailures"],
                    [],
                    f"{ACCESSIBILITY_AUDIT['checks'][3]}: {audit}",
                )

                page.keyboard.press("Escape")
                page.keyboard.press("Tab")
                focused = page.evaluate(
                    """() => {
                      const style = getComputedStyle(document.activeElement);
                      return style.outlineStyle !== "none" &&
                        parseFloat(style.outlineWidth) >= 2;
                    }"""
                )
                self.assertTrue(focused, ACCESSIBILITY_AUDIT["checks"][4])

                page.emulate_media(reduced_motion="reduce")
                reduced_motion = page.evaluate(
                    """() => ({
                      scrollBehavior: getComputedStyle(document.documentElement)
                        .scrollBehavior,
                      transitionDuration: parseFloat(getComputedStyle(
                        document.querySelector("button")
                      ).transitionDuration),
                    })"""
                )
                self.assertEqual(
                    reduced_motion["scrollBehavior"],
                    "auto",
                    ACCESSIBILITY_AUDIT["checks"][5],
                )
                self.assertLess(
                    reduced_motion["transitionDuration"],
                    0.001,
                    ACCESSIBILITY_AUDIT["checks"][5],
                )

                page.get_by_test_id("result-card").first.locator(
                    "button.card-button"
                ).click()
                expect(page.get_by_role("region", name="Media viewer")).to_be_visible()
                expect(
                    page.get_by_role("group", name="Playback controls")
                ).to_be_visible()
                page.get_by_test_id("keyboard-help").click()
                dialog = page.get_by_role("dialog", name="Keyboard shortcuts")
                expect(dialog).to_be_visible()
                self.assertEqual(dialog.get_attribute("aria-modal"), "true")
            finally:
                browser.close()


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    del standard_tests, pattern
    return loader.loadTestsFromTestCase(AccessibilityAuditBrowserTests)


if __name__ == "__main__":
    unittest.main()
