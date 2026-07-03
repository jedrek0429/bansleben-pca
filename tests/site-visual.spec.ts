import { expect, test } from '@playwright/test';

const visualRoutes = [
  { name: 'en-home', path: '/en/' },
  { name: 'fr-home', path: '/fr/' },
  { name: 'hr-home', path: '/hr/' },
  { name: 'en-contact', path: '/en/contact/' },
  { name: 'fr-contact', path: '/fr/formulaire/' },
  { name: 'hr-contact', path: '/hr/kontakt/' },
];

async function stabilize(page: import('@playwright/test').Page, path: string) {
  await page.goto(path, { waitUntil: 'networkidle' });
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

test.describe('visual regression baselines', () => {
  test.skip(
    process.env.PCA_VISUAL_REGRESSION !== '1',
    'Visual regression is opt-in until baseline screenshots are committed. Run `npm run snapshots:update` first.'
  );

  for (const route of visualRoutes) {
    test(`${route.name} top of page matches baseline`, async ({ page }, testInfo) => {
      await stabilize(page, route.path);
      await expect(page).toHaveScreenshot(`${route.name}-${testInfo.project.name}-top.png`, {
        fullPage: true,
      });
    });
  }

  test('mobile menu open state matches baseline', async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await stabilize(page, '/hr/');
    await page.locator('.mobile_menu_bar').click();
    await expect(page.locator('.mobile_nav')).toHaveClass(/opened/);

    await expect(page).toHaveScreenshot(`hr-home-${testInfo.project.name}-mobile-menu-open.png`, {
      fullPage: true,
    });
  });

  test('scrolled header state matches baseline', async ({ page }, testInfo) => {
    await stabilize(page, '/en/');
    await page.evaluate(() => window.scrollTo(0, 900));
    await expect(page.locator('#main-header')).toHaveClass(/et-fixed-header/);

    await expect(page).toHaveScreenshot(`en-home-${testInfo.project.name}-scrolled-header.png`, {
      fullPage: true,
    });
  });
});
