import { test, expect } from "@playwright/test";

test("full user journey: register, create todo, toggle completion, and logout", async ({
  page,
}) => {
  const email = `journey-${Date.now()}@example.com`;
  const password = "Password@123";
  const todoTitle = "Playwright journey todo";

  await page.goto("/register");
  await expect(page).toHaveURL(/\/register$/);

  await page.getByLabel("Email").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('input[name="confirmPassword"]').fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Todo App" })).toBeVisible();

  await page.getByRole("button", { name: /add todo/i }).click();
  await page.getByLabel("Title").fill(todoTitle);
  await page.getByLabel("Description (optional)").fill("Created through Playwright");
  await page.getByRole("button", { name: "Create" }).click();

  await expect(page.getByText(todoTitle)).toBeVisible();
  await expect(page.getByText("Created through Playwright")).toBeVisible();

  await page.getByRole("checkbox").first().click();
  await expect(page.locator("label", { hasText: todoTitle }).first()).toHaveClass(/line-through/);

  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
