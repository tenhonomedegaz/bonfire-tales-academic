import { Client, GatewayIntentBits, Options, Partials, Collection } from 'discord.js';

import {
  IDiscordCommand,
  IDiscordContextMenu,
  IGuildSettings,
  IBotEnhanced,
} from '@/modules/discord/types';
import { commands } from '@/modules/discord/commands';
import { events } from '@/modules/discord/events';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { ISchedulerProvider } from '@/shared/providers/SchedulerProvider/models/ISchedulerProvider';
import { IKeyValueStoreProvider } from '@/shared/providers/KeyValueStoreProvider/models/IKeyValueStoreProvider';
import { DeployApplicationGuildCommandsUseCase } from '@/modules/discord/useCases/DeployApplicationGuildCommandsUseCase';
import { DeleteApplicationGuildCommandsUseCase } from './useCases/DeleteApplicationGuildCommandsUseCase';

interface BotConfig {
  botName: string;
  botToken: string;
  clientId: string;
  logger: ILoggerProvider;
  scheduler: ISchedulerProvider;
  store?: IKeyValueStoreProvider;
}

export class DiscordBot {
  private client: Client;

  private botName: string;

  private clientId: string;

  private commands: Collection<string, IDiscordCommand | IDiscordContextMenu>;

  private guildSettings: Collection<string, IGuildSettings>;

  private events: Collection<string, any>;

  private cooldowns: Collection<string, Collection<string, number>>;

  private logger: ILoggerProvider;

  private scheduler: ISchedulerProvider;

  private store?: IKeyValueStoreProvider;

  constructor(private config: BotConfig) {
    const botIntents = [
  GatewayIntentBits.Guilds,
  GatewayIntentBits.GuildMembers,
  GatewayIntentBits.GuildMessages,
  GatewayIntentBits.GuildEmojisAndStickers,
  GatewayIntentBits.GuildMessageReactions,
  GatewayIntentBits.DirectMessages,
  GatewayIntentBits.MessageContent,
	];

    this.client = new Client({
      intents: botIntents,
      allowedMentions: { parse: ['users', 'roles', 'everyone'], repliedUser: true },
	  partials: [Partials.Channel, Partials.Message, Partials.Reaction, Partials.GuildMember, Partials.User],

      makeCache: Options.cacheWithLimits({
        MessageManager: 200, // This is default
        PresenceManager: 0,
        // Add more class names here
      }),
    });

    this.botName = config.botName;
    this.clientId = config.clientId;

    this.guildSettings = new Collection();
    this.commands = new Collection();
    this.events = new Collection();
    this.cooldowns = new Collection();

    this.logger = this.config.logger || console;
	console.log("DiscordBot.logger is:", this.logger);
    this.scheduler = this.config.scheduler;
    this.store = this.config.store;
  }

  private loadCommands(): this {
    commands.forEach((command, index) => {
	if (!command) {
		this.logger.log('error', `Command is undefined at index: ${index}`);
		return;
	}
	
	if (!command.commandData) {
		this.logger.log('error', `Command missing commandData: ${JSON.stringify(command, null, 2)}`);
		return;
	}
	
	if (!command.commandData.name) {
		this.logger.log('error', `Command missing commandData.name: ${JSON.stringify(command.commandData, null, 2)}`);
		return;
	}
	
	this.logger.log('info', `Command Loaded => ${command.commandData.name}`);
	
	this.commands?.set(command.commandData.name, command);
	});

    return this;
  }

  private loadEvents(): this {
    events.forEach((event) => {
      this.logger.log('info', `Event Loaded => ${event.name}`);

      const bot: IBotEnhanced = {
        botName: this.botName,
		client: this.client,
        guildSettings: this.guildSettings,
        commands: this.commands,
        events: this.events,
        cooldowns: this.cooldowns,
        logger: this.logger,
        scheduler: this.scheduler,
        store: this.store,
      };

      if (event.once) {
        this.client.once(event.name, (...args: any[]) => event.execute(bot, ...(args as [any])));
      } else {
        this.client.on(event.name, (...args: any[]) => event.execute(bot, ...(args as [any])));
      }
    });

    this.client.on('shardError', (error) =>
      this.logger.log('error', 'A websocket connection encountered an error:', error),
    );
    this.client.on('warn', (warn) => this.logger.log('warn', warn));
    this.client.on('error', (error) => this.logger.log('error', 'Error', error));
    this.client.on('debug', (debug) => this.logger.log('debug', debug));

    return this;
  }

  async syncGuildCommands({ discordGuildId }: { discordGuildId: string }): Promise<void> {
    try {
      const deployApplicationGuildCommandsUseCase = new DeployApplicationGuildCommandsUseCase();

      await deployApplicationGuildCommandsUseCase.execute({
        discordClientId: this.clientId,
        discordGuildId,
      });

    } catch (error) {
      this.logger.log('error', 'syncGuildCommands', error);
    }
  }

  async deleteGuildCommands({ discordGuildId }: { discordGuildId: string }): Promise<void> {
    try {
      const deleteApplicationGuildCommandsUseCase = new DeleteApplicationGuildCommandsUseCase();

      await deleteApplicationGuildCommandsUseCase.execute({
        discordClientId: this.clientId,
        discordGuildId,
      });
    } catch (error) {
      this.logger.log('error', 'deleteGuildCommands', error);
    }
  }

  async loadGuildSettings({ discordGuildId }: { discordGuildId: string }): Promise<void> {
    const guildSettings = await this.store?.get(discordGuildId);

    if (guildSettings) {
      const settings = JSON.parse(guildSettings);

      this.guildSettings.set(discordGuildId, settings);
      // const { prefix } = message.client.guildSettings.get(message.guild.id);
    }

    this.logger.log('info', 'Guild Settings loaded!');
  }

  async shutDown(): Promise<void> {
    await this.scheduler?.stop();

    this.client.destroy();
  }

  async startUp(): Promise<void> {
  try {
    this.loadCommands().loadEvents();

    if (this.scheduler) {
      this.scheduler?.setBotClient(this.client);
      await this.scheduler?.start();
    }

    this.client.once("ready", async () => {
      this.logger.log("info", "Syncing slash commands...");
      const guildIds = (process.env.TEST_GUILD_ID || '').split(',').map(id => id.trim()).filter(Boolean);
      for (const gId of guildIds) {
        await this.syncGuildCommands({ discordGuildId: gId });
      }

      // Load default recurring jobs for all connected guilds
      if (this.scheduler) {
        for (const [gId, guild] of this.client.guilds.cache) {
          await this.scheduler?.loadDefaultJobs({ guildId: gId });
          this.logger.log("info", `Loaded default scheduler jobs for guild: ${gId} (${guild.name})`);
        }
      }
    });

    this.client.login(this.config.botToken);

  } catch (error) {
    this.logger.log("error", `BOT ${this.botName} startUp Error`, error);

    await this.shutDown();
  }
}

}
