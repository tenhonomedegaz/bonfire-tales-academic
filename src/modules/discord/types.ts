import {
  Collection,
  ChannelType,
  ChatInputCommandInteraction,
  Client,
  ContextMenuCommandInteraction,
  AutocompleteInteraction,
  PermissionResolvable,
} from 'discord.js';
import { ContextMenuCommandBuilder } from '@discordjs/builders';

import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { ISchedulerProvider } from '@/shared/providers/SchedulerProvider/models/ISchedulerProvider';
import { IKeyValueStoreProvider } from '@/shared/providers/KeyValueStoreProvider/models/IKeyValueStoreProvider';

export interface IGuildSettings {
  [key: string]: unknown;
}

export type IDiscordChannelType = ChannelType;

export const ChannelTypes: { [key: string]: IDiscordChannelType } = {
  TEXT: ChannelType.GuildText,
  NEWS: ChannelType.GuildAnnouncement,
  NEWS_THREAD: ChannelType.AnnouncementThread,
  PUBLIC_THREAD: ChannelType.PublicThread,
  PRIVATE_THREAD: ChannelType.PrivateThread,
  DM: ChannelType.DM,
};

export const DiscordApplicationCommandTypes = {
  CHAT_INPUT: 1,
  USER_CONTEXT: 2,
  MESSAGE_CONTEXT: 3,
};

export interface IBotEnhanced {
  botName: string;
  client?: Client;
  // eslint-disable-next-line no-use-before-define
  commands: Collection<string, IDiscordCommand | IDiscordContextMenu>;
  guildSettings: Collection<string, IGuildSettings>;
  events: Collection<string, unknown>;
  // events?: Collection<string, IDiscordMessageEvent>;
  cooldowns: Collection<string, Collection<string, number>>;
  logger: ILoggerProvider;
  scheduler: ISchedulerProvider;
  store?: IKeyValueStoreProvider;
}

export interface IDiscordCommand {
  commandData: any;
  cooldown?: number;
  allowedChannelTypes?: IDiscordChannelType[];
  allowedRoles?: string[];
  requiredPermissions?: PermissionResolvable[];
  rootAdminOnly?: boolean;
  autocomplete?: any;
  execute(
    bot: IBotEnhanced,
    interaction: any,
    commandArgs?: any[],
  ): void | Promise<unknown | void>;
}
export interface IDiscordContextMenu {
  commandData: ContextMenuCommandBuilder;
  cooldown?: number;
  allowedChannelTypes?: IDiscordChannelType[];
  allowedRoles?: string[];
  requiredPermissions?: PermissionResolvable[];
  rootAdminOnly?: boolean;
  execute(
    bot: IBotEnhanced,
    interaction: any,
    commandArgs?: any[],
  ): void | Promise<unknown | void>;
}

export interface IDiscordAutocomplete {
  commandsToRespond: string[];
  execute(bot: IBotEnhanced, interaction: AutocompleteInteraction): void | Promise<unknown | void>;
}
