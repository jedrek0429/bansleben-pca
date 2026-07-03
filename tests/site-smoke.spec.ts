import { expect, Page, test } from '@playwright/test';

const routes = [
  { lang: 'en', home: '/en/', contact: '/en/contact/' },
  { lang: 'fr', home: '/fr/', contact: '/fr/formulaire/' },
  { lang: 'hr', home: '/hr/', contact: '/hr/kontakt/' },
];

async function gotoOk(page: Page, path: string) {
  const response = await page.goto(path, { waitUntil: 'domcontentloaded' });
  expect(response, `Expected ${path} to return a response`).not.toBeNull();
  expect(response!.status(), `Expected ${path} to load successfully`).toBeLessThan(400);
}

test.describe('static PCA site smoke tests', () => {
  for (const route of routes) {
    test(`${route.lang} home renders core layout`, async ({ page }) => {
      await gotoOk(page, route.home);

      await expect(page.locator('#main-header')).toBeVisible();
      await expect(page.locator('#page-container')).toBeVisible();
      await expect(page.locator('#main-content')).toBeVisible();
      await expect(page.locator('#main-footer')).toBeVisible();

      const menuLinkCount = await page.locator('#top-menu a').count();
      expect(menuLinkCount).toBeGreaterThan(1);
    });

    test(`${route.lang} contact form keeps static POST behavior`, async ({ page }) => {
      await gotoOk(page, route.contact);

      const form = page.locator('form.static_contact_form');
      await expect(form).toBeVisible();
      await expect(form).toHaveAttribute('method', /post/i);
      await expect(form).toHaveAttribute('action', /contact\.php$/);
      await expect(form.locator('input[name="name"]')).toBeVisible();
      await expect(form.locator('input[name="email"]')).toBeVisible();
      await expect(form.locator('textarea[name="message"]')).toBeVisible();
      await expect(form.locator('input[name="lang"]')).toHaveValue(route.lang);
      await expect(form.locator('input[name="website"]')).toBeAttached();
    });
  }

  test('mobile navigation opens and closes on the Croatian homepage', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await gotoOk(page, '/hr/');

    const mobileNav = page.locator('.mobile_nav');
    const toggle = page.locator('.mobile_menu_bar');
    await expect(toggle).toBeVisible();

    await toggle.click();
    await expect(mobileNav).toHaveClass(/opened/);
    await expect(page.locator('#mobile_menu')).toBeVisible();

    await toggle.click();
    await expect(mobileNav).toHaveClass(/closed/);
  });

  test('header remains fixed while scrolling', async ({ page }) => {
    await gotoOk(page, '/en/');

    const header = page.locator('#main-header');
    await expect(header).toBeVisible();

    await expect(header).toHaveCSS('position', 'fixed');

    const before = await header.boundingBox();
    expect(before, 'Expected header bounding box before scrolling').not.toBeNull();

    await page.evaluate(() => window.scrollTo(0, 900));
    await page.waitForFunction(() => window.scrollY > 0 || document.documentElement.scrollTop > 0);

    const after = await header.boundingBox();
    expect(after, 'Expected header bounding box after scrolling').not.toBeNull();
    expect(Math.abs(after!.y - before!.y)).toBeLessThanOrEqual(1);
  });
});