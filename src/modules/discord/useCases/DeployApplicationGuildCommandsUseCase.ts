import { Routes } from 'discord-api-types/v9';
import { ApplicationCommandPermissionType } from 'discord-api-types/payloads/v9';

import { commands } from '@/modules/discord/commands';
import { bonfireBotAdminUserIds } from '@/config/bonfire';
import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { discordApi } from '@/shared/services/discordApi';

interface IRequest {
  discordClientId: string;
  discordGuildId: string;
}

export class DeployApplicationGuildCommandsUseCase implements IBaseUseCase {
  public async execute({ discordClientId, discordGuildId }: IRequest): Promise<void> {
  const guildCommandsData = [];
  const rootAdminOnlyCommandNames = new Set<string>();

  commands.forEach((command, index) => {
    // 1. Check if command exists
    if (!command) {
      console.log(`❌ Command at index ${index} is undefined.`);
      return;
    }

    // 2. Check if commandData exists
    if (!command.commandData) {
      console.log(`❌ Command missing commandData:`, command);
      return;
    }

    // 3. Check if commandData.toJSON exists
    if (typeof command.commandData.toJSON !== "function") {
      console.log(`❌ commandData.toJSON is not a function for command:`, command.commandData);
      return;
    }

    // Permission checks are handled by the bot at runtime. Discord's old
    // per-command permission endpoint is deprecated and does not support our
    // bot-admin user override.
    const jsonData = command.commandData.toJSON();

    if (command.rootAdminOnly) {
      rootAdminOnlyCommandNames.add(jsonData.name);
      jsonData.default_permission = false;
    }

    guildCommandsData.push(jsonData);
  });

  console.log("📤 Prepared slash commands payload:", guildCommandsData);

  await discordApi.put(
    Routes.applicationGuildCommands(discordClientId, discordGuildId),
    { body: guildCommandsData }
  );

  // Note: Per-command application command permissions API is deprecated and returns 403 (20001) for bots.
  // Permissions should be managed directly within Discord guild settings integrations dashboard.
  /*
  if (rootAdminOnlyCommandNames.size === 0 || bonfireBotAdminUserIds.length === 0) {
    return;
  }

  try {
    const registeredCommands = await discordApi.get(
      Routes.applicationGuildCommands(discordClientId, discordGuildId),
    ) as any[];

    await Promise.all(
      registeredCommands
        .filter((command) => rootAdminOnlyCommandNames.has(command.name))
        .map((command) =>
          discordApi.put(
            Routes.applicationCommandPermissions(discordClientId, discordGuildId, command.id),
            {
              body: {
                permissions: bonfireBotAdminUserIds.map((userId) => ({
                  id: userId,
                  type: ApplicationCommandPermissionType.User,
                  permission: true,
                })),
              },
            },
          ),
        ),
    );
  } catch (error) {
    console.warn('Nao foi possivel restringir a visibilidade dos comandos root-admin.', error);
  }
  */
}
}
