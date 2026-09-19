import { test, expect, type Page } from "@playwright/test";

async function registerUser(page: Page, email: string, password: string) {
  await page.goto("/register");
  await expect(page).toHaveURL(/\/register$/);

  await page.getByLabel("Email").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('input[name="confirmPassword"]').fill(password);
  await page.getByRole("button", { name: "Create Account" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Todo App" })).toBeVisible();
}

async function createTodo(page: Page, title: string, description: string) {
  await page.getByRole("button", { name: /add todo/i }).click();
  await page.getByLabel("Title").fill(title);
  await page.getByLabel("Description (optional)").fill(description);
  await page.getByRole("button", { name: "Create" }).click();

  await expect(page.getByText(title)).toBeVisible();
  await expect(page.getByText(description)).toBeVisible();
}

test("cross-user data isolation: user B cannot see user A's private todo", async ({
  browser,
}) => {
  const password = "Password@123";
  const userAEmail = `usera-${Date.now()}@example.com`;
  const userBEmail = `userb-${Date.now()}@example.com`;
  const todoTitle = `Private Todo ${Date.now()}`;
  const todoDescription = "This item should remain private to user A";

  const contextA = await browser.newContext();
  const contextB = await browser.newContext();

  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await registerUser(pageA, userAEmail, password);
    await createTodo(pageA, todoTitle, todoDescription);

    await pageA.getByRole("button", { name: "Logout" }).click();
    await expect(pageA).toHaveURL(/\/login$/);

    await registerUser(pageB, userBEmail, password);

    await expect(pageB.getByText(todoTitle)).toHaveCount(0);
    await expect(pageB.getByText("No todos yet")).toBeVisible();
    await expect(
      pageB.getByText("Create your first todo to get started")
    ).toBeVisible();
  } finally {
    await contextA.close();
    await contextB.close();
  }
});
