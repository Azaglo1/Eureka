const path = require("path");
const dotenv = require("dotenv");
const { z } = require("zod");

dotenv.config({ path: path.resolve(__dirname, "../../.env") });

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().min(1),
  SESSION_SECRET: z.string().min(24),
  SESSION_STORE: z.enum(["memory", "postgres"]).default("postgres"),
  SMTP_HOST: z.string().default("smtp.gmail.com"),
  SMTP_PORT: z.coerce.number().int().positive().default(587),
  SMTP_USER: z.string().optional().default(""),
  SMTP_PASS: z.string().optional().default(""),
  WHATSAPP_TOKEN: z.string().optional().default(""),
  WHATSAPP_PHONE_NUMBER_ID: z.string().optional().default(""),
  SMS_PROVIDER: z.string().optional().default(""),
  SMS_API_KEY: z.string().optional().default(""),
  SMS_API_URL: z.string().optional().default(""),
  SMS_SENDER_ID: z.string().optional().default("")
});

const env = envSchema.parse(process.env);

module.exports = { env };
