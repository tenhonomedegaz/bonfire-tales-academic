// fix import 'dotenv/config'; not working with babel
import path from 'path';
import dotenv from 'dotenv';
import * as enValid from 'envalid';

const envPath = path.resolve(__dirname, '..', '..', '..', '.env');
dotenv.config({ path: envPath });

export const env = enValid.cleanEnv(process.env, {
  NODE_ENV: enValid.str({
    choices: ['development', 'test', 'production'],
    default: 'development',
  }),
  DISCORD_BOT_TOKEN: enValid.str(),
  DISCORD_BOT_NAME: enValid.str(),
  DISCORD_CLIENT_ID: enValid.str(),

  DATABASE_URL: enValid.str({ default: '' }),
  BONFIRE_SITE_URL: enValid.url({ default: 'https://bonfiretales.com.br' }),
  BONFIRE_CHECKOUT_SIGNING_SECRET: enValid.str({ default: '' }),

  // APP_API_URL: enValid.url({
  //   example: 'http://localhost:3333',
  //   devDefault: 'http://localhost:3333',
  // }),
  // POSTGRES_HOST: enValid.str({
  //   devDefault: 'localhost',
  //   example: 'localhost',
  // }),
  // POSTGRES_PORT: enValid.port({
  //   devDefault: 5432,
  //   example: '5432',
  // }),
  // AWS_SES_REGION: enValid.str({
  //   default: process.env.MAIL_DRIVER === 'ethereal' ? '' : undefined,
  // }),
});
