/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { container } from 'tsyringe';
import {
  ChannelType,
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  Guild,
  TextChannel,
} from 'discord.js';
import { differenceInMinutes, subMinutes } from 'date-fns';

import { IBaseJob, BotClient } from '@/shared/providers/SchedulerProvider/models/IBaseJob';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import {
  bonfireChannels,
  bonfireRpgRankRoles,
  RpgRankRole,
} from '@/config/bonfire';

import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { questInfoEmbedMessage } from '@/modules/discord/commands/bonfire/rpg/quests/questEmbeds';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';

interface JobData {
  guildId: string;
  questId: string;
}

interface JobRequest {
  botClient: BotClient;
  logger: ILoggerProvider;
  jobData: JobData;
}

async function findHighestRankRoleName({
  allowedQuestRolesIds,
  rpgRankRolesList,
  guild,
}: {
  allowedQuestRolesIds: string[];
  rpgRankRolesList: RpgRankRole[];
  guild: Guild;
}): Promise<string> {
  const guildRoles = await guild.roles.fetch();

  const selectedRoles = guildRoles
    .filter((role) => allowedQuestRolesIds.includes(role.id))
    .map((role) => {
      const rankOrder = rpgRankRolesList.find(
        (r) => r.name.toUpperCase() === role.name.toUpperCase(),
      )?.rank;

      if (!rankOrder) {
        throw new Error(`Could not define rank order for role (${role.id})`);
      }

      return { roleId: role.id, roleName: role.name, rankOrder };
    })
    .sort((a, b) => b.rankOrder - a.rankOrder);

  if (selectedRoles.length === 0) {
    throw new Error('Could not define rank order');
  }

  return selectedRoles[0].roleName;
}

export class PublishQuestJob implements IBaseJob {
  public static jobName = 'quest-publish';

  public async execute({ botClient, logger, jobData }: JobRequest): Promise<void> {
    try {
      const discordGuild = await botClient.guilds.fetch(jobData.guildId);

      if (!discordGuild) {
        logger.log('error', `Guild not found (${jobData.guildId})`);
        return;
      }

      await discordGuild.channels.fetch();

      const logChannel = discordGuild.channels.cache.find(
        (ch) =>
          ch.type === ChannelType.GuildText &&
          ch.name === bonfireChannels.logChannelName,
      ) as TextChannel | undefined;

      if (!logChannel) {
        logger.log('error', `Log channel not found (${bonfireChannels.logChannelName})`);
        return;
      }

      const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
      const quest = await showQuestByIdUseCase.execute(jobData.questId);

      if (!quest) {
        await logChannel.send(`Error: Quest \`${jobData.questId}\` not found.`);
        return;
      }

      const highestRankRoleName = await findHighestRankRoleName({
        allowedQuestRolesIds: quest.allowedRanks,
        rpgRankRolesList: bonfireRpgRankRoles,
        guild: discordGuild,
      });

      let questsChannelCategory = discordGuild.channels.cache.find(
        (c) =>
          c.type === ChannelType.GuildCategory &&
          c.name.toUpperCase() === highestRankRoleName.toUpperCase(),
      );

      if (!questsChannelCategory) {
        questsChannelCategory = discordGuild.channels.cache.find(
          (c) =>
            c.type === ChannelType.GuildCategory &&
            c.name.toLowerCase().includes(highestRankRoleName.toLowerCase()),
        );
      }

      if (!questsChannelCategory) {
        await logChannel.send(
          `Error: category \`${highestRankRoleName}\` not found for quest \`${quest.id}\`.`
        );
        return;
      }

      const questChannelName = quest.name.substring(0, 90);

      const questChannel = await discordGuild.channels.create({
        name: questChannelName,
        type: ChannelType.GuildText,
        parent: questsChannelCategory.id,
      });

      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);

      quest.isPublished = true;
      quest.channelId = questChannel.id;

      const updatedQuest = await updateQuestUseCase.execute(quest);

      const questInfoMessage = await questInfoEmbedMessage({
		quest: updatedQuest,
		showQueueList: false,
	  });

	  questInfoMessage.setFooter({ text: String(updatedQuest.id) });

      const actionRow = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
          .setCustomId(`quest-join:${updatedQuest.id}`)
          .setLabel('Participar')
          .setStyle(ButtonStyle.Success),
        new ButtonBuilder()
          .setCustomId(`quest-leave:${updatedQuest.id}`)
          .setLabel('Desistir')
          .setStyle(ButtonStyle.Secondary),
      );

      await questChannel.send({
		content: `${quest.allowedRanks.map((id) => `<@&${id}>`).join('\n')}`,
		embeds: [questInfoMessage],
		components: [actionRow],
	  });

    } catch (error) {
      logger.log('error', 'Error in PublishQuestJob', error);
    }
  }
}
