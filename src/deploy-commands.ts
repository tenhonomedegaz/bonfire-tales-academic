import "reflect-metadata";
import "dotenv/config";
import { REST, Routes } from "discord.js";
import fs from "fs";
import path from "path";

const clientId = process.env.DISCORD_CLIENT_ID as string;
const guildId = process.env.TEST_GUILD_ID as string;
const token = process.env.DISCORD_BOT_TOKEN as string;

process.stdout.write("DEBUG: Starting deploy script...\n");

if (!clientId || !guildId || !token) {
  process.stdout.write("ERROR: Missing environment variables.\n");
  process.exit(1);
}

const commandsDir = path.join(__dirname, "modules", "discord", "commands");
process.stdout.write(`DEBUG: Commands dir = ${commandsDir}\n`);

function loadCommandsRecursively(dir: string) {
  process.stdout.write(`DEBUG: Loading dir: ${dir}\n`);
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  const commands: any[] = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      commands.push(...loadCommandsRecursively(fullPath));
      continue;
    }

    if (!entry.name.endsWith(".js")) continue;

    process.stdout.write("DEBUG: Loading file: " + fullPath + "\n");

    const commandFile = require(fullPath);
    const command = commandFile.default || commandFile;

    if (!command || !command.data) {
      process.stdout.write("DEBUG: File has no command data.\n");
      continue;
    }

    commands.push(command.data.toJSON());
  }

  return commands;
}

const commands = loadCommandsRecursively(commandsDir);
process.stdout.write(`DEBUG: Loaded ${commands.length} commands.\n`);

const rest = new REST({ version: "10" }).setToken(token);

(async () => {
  try {
    process.stdout.write("DEBUG: Sending commands to Discord...\n");

    const guildIds = (guildId || "").split(',').map(id => id.trim()).filter(Boolean);

    for (const gId of guildIds) {
      process.stdout.write(`DEBUG: Deploying to guild ${gId}...\n`);
      await rest.put(
        Routes.applicationGuildCommands(clientId, gId),
        { body: commands }
      );
    }

    process.stdout.write("SUCCESS: Commands deployed to all guilds!\n");
  } catch (err) {
    process.stdout.write("ERROR: Deploy failed.\n");
    process.stdout.write(JSON.stringify(err, null, 2));
  }
})();
