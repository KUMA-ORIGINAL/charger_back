import { expect, test as setup } from '@playwright/test'

/**
 * Один вход на весь прогон: сессия сохраняется и переиспользуется тестами.
 * Входить в каждом тесте нельзя — параллельные входы одним номером упираются
 * в защиту от перебора пароля (5 попыток за 15 минут).
 * Учётка — суперпользователь, задаётся E2E_PHONE и E2E_PASSWORD.
 */

export const STORAGE_STATE = 'e2e/.auth/owner.json'

const PHONE = process.env.E2E_PHONE ?? ''
const PASSWORD = process.env.E2E_PASSWORD ?? ''

setup('sign in', async ({ page }) => {
  await page.goto('./')
  await expect(page).toHaveURL(/\/panel\/login/)
  await page.getByLabel('Телефон').fill(PHONE)
  await page.getByLabel('Пароль', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти' }).click()
  await expect(page.getByRole('heading', { name: 'Обзор сети' })).toBeVisible()
  await page.context().storageState({ path: STORAGE_STATE })
})
