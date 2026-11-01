import { expect, test } from '@playwright/test'

/**
 * Смоук по живому бэкенду с данными (станция, сессия, платёж) и суперпользователем:
 * дашборд и каждый раздел открываются без ошибок. Вход — в auth.setup.ts.
 */

test('dashboard shows totals and stations', async ({ page }) => {
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Обзор сети' })).toBeVisible()
  await expect(page.getByText('Выручка', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Станции', exact: true })).toBeVisible()
})

for (const [key, title] of [
  ['chargepoint', 'Станции'],
  ['chargingsession', 'Сессии зарядки'],
  ['csmsservice', 'CSMS-сервисы'],
  ['qrpayment', 'QR-платежи'],
  ['user', 'Пользователи'],
] as const) {
  test(`section «${title}» opens a list and a detail page`, async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))

    await page.goto(`./r/${key}`)
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
    // Ссылка в первой колонке появляется, когда пришли данные (а не скелетон).
    const firstLink = page.getByRole('table').getByRole('link').first()
    await expect(firstLink).toBeVisible()
    await firstLink.click()
    await expect(page).toHaveURL(new RegExp(`/panel/r/${key}/[w-]+`))
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    expect(errors).toEqual([])
  })
}

test('session filters live in the URL', async ({ page }) => {
  await page.goto('./r/chargingsession?status=charging')
  await expect(page.getByRole('button', { name: 'Убрать фильтр «Статус»' })).toBeVisible()
})

test('command palette jumps to a section', async ({ page }) => {
  await page.goto('./')
  await expect(page.getByRole('heading', { name: 'Обзор сети' })).toBeVisible()
  await page.keyboard.press('Control+k')
  await page.getByPlaceholder('Раздел, действие или номер сессии…').fill('QR')
  await page
    .getByRole('option', { name: /QR-платежи/ })
    .first()
    .click()
  await expect(page).toHaveURL(/\/panel\/r\/qrpayment/)
})

test('unknown section shows not found', async ({ page }) => {
  await page.goto('./r/nope')
  await expect(page.getByRole('heading', { name: 'Страница не найдена' })).toBeVisible()
})
