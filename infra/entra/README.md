# Entra External ID Setup

One-time manual steps to create the Entra External ID tenant and app registration.
The resulting IDs go into `infra/main.bicepparam`.

Sources verified against Microsoft Learn docs updated April 8, 2025 and November 6, 2025.

---

## Step 1 — Create the External ID tenant

1. Go to **https://entra.microsoft.com** and sign in with the account that owns your Azure subscription.

2. In the left nav, open **Entra ID**.

3. Click **Overview**.

4. Click **Manage tenants**.

5. Click **+ Create**.

6. Select **External** → click **Continue**.

7. On the **Basics** tab fill in:
   - **Tenant name**: `Victros`
   - **Domain name**: `victros` — becomes `victros.onmicrosoft.com`. Must be globally unique; if taken try `victros-app` etc.
   - **Location/Country**: United States — cannot be changed later.

8. Complete the subscription step if shown:
   - **Subscription**: `Victros-Azure` (<YOUR_SUBSCRIPTION_ID>)
   - **Resource group**: create new → `rg-victros-entra`

9. Click **Review + create** → **Create**. Wait up to 30 minutes.

10. When provisioning completes, switch into the new tenant using the directory switcher at the top right (Settings icon → Directories + subscriptions → Switch next to `victros.onmicrosoft.com`).

11. Go to **Entra ID** → **Overview** and copy the **Tenant ID** — this is `entraTenantId` in `main.bicepparam`.

> **Note:** After creation, the external tenant can be accessed from both entra.microsoft.com and portal.azure.com. But creation must be done from entra.microsoft.com.

---

## Step 2 — Register the Victros application

Make sure you are switched into the `victros` external tenant before doing this.

1. In the left nav, go to **Entra ID** → **App registrations**.

2. Click **+ New registration**.

3. Fill in:
   - **Name**: `Victros`
   - **Supported account types**: Accounts in this organizational directory only (single tenant)
   - **Redirect URI**: leave blank for now

4. Click **Register**.

5. On the app **Overview** page, copy the **Application (client) ID** — this is `entraClientId` in `main.bicepparam`.

---

## Step 3 — Grant admin consent

In external tenants, users cannot self-consent to permissions. You must grant consent as admin.

1. From the app Overview, click **API permissions** in the left menu.
2. Click **Grant admin consent for Victros**.
3. Click **Yes** → then **Refresh**.
4. The **Status** column should show **Granted for Victros**.

---

## Step 4 — Create app roles (for snapshot admin access)

1. From the app Overview, click **App roles** in the left menu.
2. Click **+ Create app role**.
3. Fill in:
   - **Display name**: `Snapshot Generator`
   - **Allowed member types**: Users/Groups
   - **Value**: `snapshot.generate`  ← must match exactly
   - **Description**: Can trigger weekly pipeline risk snapshot generation
4. Ensure **Enable this app role** is checked → click **Apply**.

---

## Step 5 — Create a user flow (sign-in page)

1. In the left nav, go to **External Identities** → **User flows**.
2. Click **+ New user flow**.
3. Fill in:
   - **Name**: `SignInSignUp`
   - **Identity providers**: Email with password
4. Under **User attributes**, check: **Email Address**, **Display Name**.
5. Click **Create**.

---

## Step 6 — Update main.bicepparam

Open `infra/main.bicepparam` and fill in:

```
param entraTenantId = '<tenant-id-from-step-1>'
param entraClientId = '<client-id-from-step-2>'
```

---

## Step 7 — After infrastructure deploy (post-Bicep steps)

1. Get `frontendUrl` from the Bicep deployment output.
2. In the app registration → **Authentication** → **+ Add a platform** → **Web**.
   - Redirect URI: `https://<frontendUrl>/.auth/login/aad/callback`
   - Click **Configure**.
3. Under **Implicit grant and hybrid flows**, check **ID tokens** → **Save**.
4. Assign the `snapshot.generate` role to admin users:
   - Go to **Entra ID** → **Enterprise applications** → find **Victros**.
   - Click **Users and groups** → **+ Add user/group**.
   - Select the admin users → assign **Snapshot Generator** role → click **Assign**.

---

## Prerequisite note

If the **Create** button in Manage tenants is missing or disabled, your account may not have the **Tenant Creator** role. Check with whoever administers the Azure account.
