# WhatsApp Business API Integration & Buyer's Guide

This guide explains how to purchase, configure, and connect a WhatsApp Business API account to **Farm Fresh** so your customers automatically receive:
1. **Order Confirmation with Itemized Product Details** immediately upon ordering.
2. **Order Approval & Delivery Updates** when the farmer approves the order and assigns delivery slots.

---

## 1. Quick Testing Before You Buy (Simulated Mode)

You **do not need to spend any money** to test and develop with WhatsApp in this project.

The application includes a built-in **Simulation Mode**. In your `.env` file, set:
```ini
WHATSAPP_PROVIDER=console
```

When an order is placed or approved:
- The full formatted WhatsApp message is logged into `logs/django.log` and the server console.
- A delivery record marked as **Simulated (Dev)** appears in your Farmer Dashboard under **WhatsApp Notifications** (`/farmer/notifications/`).
- You can review the exact text, item breakdown, customer phone number, and delivery date.

---

## 2. Choosing Your WhatsApp API Provider

When ready to take the store into live production, you have two primary options:

| Feature | Option A: Meta WhatsApp Cloud API (Recommended) | Option B: Twilio WhatsApp API |
| :--- | :--- | :--- |
| **Provider** | Direct with Meta / Facebook | Twilio (Official Meta Partner) |
| **Cost** | Direct Meta pricing (lowest cost; ~₹0.30 - ₹0.80 per conversation in India; first 1,000 service conversations/month free) | Twilio markup on top of Meta fee |
| **Setup Speed** | 15 - 30 minutes | 5 - 10 minutes |
| **Phone Number** | Your own dedicated business phone number | Twilio number or ported business number |
| **Best For** | Direct production at lowest operating cost | Quick plug-and-play developer setup |

---

## 3. Option A: Official Meta WhatsApp Business Cloud API Setup

### Step 1: Create a Meta for Developers Account
1. Visit [Meta for Developers](https://developers.facebook.com/) and log in with your Facebook account.
2. Click **My Apps** > **Create App**.
3. Select **Other** as the use case > click **Next**.
4. Select **Business** as the app type > enter your App Name (e.g. `Farm Fresh Store`) > click **Create app**.

### Step 2: Add WhatsApp to Your App
1. On the app dashboard, scroll down to **WhatsApp** and click **Set up**.
2. Meta will automatically create a sandbox test environment and display:
   - **Temporary Access Token**
   - **Phone number ID**
   - **WhatsApp Business Account ID**

### Step 3: Register Your Real Farm Phone Number
> **Note:** The phone number used for WhatsApp Business API cannot be simultaneously active on a personal WhatsApp mobile app on a phone. If it is already on WhatsApp, back up your chats and delete the WhatsApp account from the mobile app before registering it with Meta.

1. Under **WhatsApp** > **API Setup**, scroll to **Step 5: Add a phone number**.
2. Click **Add phone number**, enter your Farm store business name and your phone number.
3. Verify the number via SMS or voice call OTP.
4. Copy your **Phone number ID** (this is different from the phone number itself).

### Step 4: Generate a Permanent Access Token
Temporary tokens expire in 24 hours. For production, generate a permanent System User token:
1. Go to [Meta Business Manager](https://business.facebook.com/settings/).
2. Navigate to **Users** > **System Users**.
3. Click **Add** to create a system user (Name: `FarmStoreBot`, Role: `Admin`).
4. Click **Generate New Token**, select your WhatsApp App, and check permissions:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
5. Copy the generated token immediately and keep it safe.

### Step 5: Update `.env` in Farm Fresh
Open `.env` on your server and set:
```ini
WHATSAPP_PROVIDER=meta
WHATSAPP_API_TOKEN=your_permanent_system_user_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
```
Restart Gunicorn:
```bash
sudo systemctl restart farmstore-gunicorn
```

---

## 4. Option B: Twilio WhatsApp API Setup

If you prefer Twilio:
1. Sign up at [Twilio.com](https://www.twilio.com/).
2. In the Twilio Console, go to **Messaging** > **Try it out** > **Send a WhatsApp message** to activate the WhatsApp Sandbox.
3. To go live, request a **WhatsApp Sender** in Twilio using your business number.
4. Find your **Account SID** and **Auth Token** on your Twilio Console Dashboard.
5. In your `.env`:
   ```ini
   WHATSAPP_PROVIDER=twilio
   TWILIO_ACCOUNT_SID=your_account_sid_here
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```

---

## 5. WhatsApp Message Rules & Template Approval

WhatsApp enforces strict anti-spam rules:
- **Customer-Initiated (24-Hour Window)**: If a customer messages your WhatsApp number first, you have a 24-hour free-form session window where you can reply with any plain text message.
- **Business-Initiated (Order Confirmations / Status Updates)**: When sending a message to a customer without them messaging you first, Meta requires pre-approved **Utility Templates** in production.

### Recommended Meta Message Template for Orders:
In Meta Business Manager > WhatsApp Manager > **Message Templates**, create:

- **Template Name**: `order_confirmation`
- **Category**: `Utility`
- **Language**: `English (en)`
- **Body**:
  ```text
  🌱 *{{1}}* — Order Confirmed!
  Order: {{2}}
  Customer: {{3}}
  Total: ₹{{4}}
  We are preparing your fresh farm harvest!
  ```

---

## 6. Farmer Dashboard Features

- **Audit Trail**: Every notification attempt is logged in `/farmer/notifications/` with recipient, status (Sent, Simulated, or Failed), and message preview.
- **Resend Update**: From any order detail page (`/farmer/orders/<order-number>/`), the farmer can click **Send / Resend WhatsApp Notification**.
- **Direct WhatsApp Chat**: One-click **Open WhatsApp Chat with Customer** button opens a direct pre-filled chat with the customer in WhatsApp Web or mobile app.
