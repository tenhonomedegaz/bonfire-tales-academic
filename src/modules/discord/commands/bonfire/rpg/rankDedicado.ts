import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';
import { ChannelType } from 'discord.js';
import { IDiscordCommand } from '@/modules/discord/types';
import { getRolesFromMentions, hasBotAdminPermission } from '@/modules/discord/util';
import { bonfireRoles, bonfireRpgRankRoles, rankWithEmoji } from '@/config/bonfire';
import {
  CalculateDedicatedRankUseCase,
  DEDICATED_RANK_VALID_RANKS,
} from '@/modules/rpg/dedicatedRank/useCases/CalculateDedicatedRankUseCase';
import { ClearDedicatedRankPriorityUseCase } from '@/modules/rpg/dedicatedRank/useCases/ClearDedicatedRankPriorityUseCase';
import { SetDedicatedRankManuallyUseCase } from '@/modules/rpg/dedicatedRank/useCases/SetDedicatedRankManuallyUseCase';
import { SetDedicatedRankPriorityUseCase } from '@/modules/rpg/dedicatedRank/useCases/SetDedicatedRankPriorityUseCase';
import { ShowCurrentDedicatedRankUseCase } from '@/modules/rpg/dedicatedRank/useCases/ShowCurrentDedicatedRankUseCase';
import { AppError } from '@/shared/errors/AppError';
import { nowInBrazil } from '@/shared/util/dateTime';


const commandData = new SlashCommandBuilder()
  .setName('rank-dedicado')
  .setDescription('Gerencia o ranque dedicado da semana')
  .addSubcommand((sub) =>
    sub
      .setName('calcular')
      .setDescription('Calcula automaticamente o ranque dedicado baseado em quests da semana'),
  )
  .addSubcommand((sub) =>
    sub
      .setName('definir')
      .setDescription('Define manualmente a ordem do ranque dedicado')
      .addStringOption((opt) =>
        opt
          .setName('ordem')
          .setDescription('Ranks em ordem de prioridade, separados por vírgula')
          .setRequired(true),
      ),
  )
  .addSubcommand((sub) =>
    sub
      .setName('priorizar')
      .setDescription('Trava um rank em 0º lugar (recompensa máxima, fora da disputa) até ser desfeita')
      .addStringOption((opt) =>
        opt
          .setName('rank')
          .setDescription('Rank que deve ficar em 0º lugar (recompensa máxima, fora da disputa)')
          .setRequired(true),
      ),
  )
  .addSubcommand((sub) =>
    sub
      .setName('desfazer-prioridade')
      .setDescription('Remove a prioridade travada do ranque dedicado'),
  )
  .addSubcommand((sub) =>
    sub
      .setName('ver')
      .setDescription('Mostra o ranque dedicado atual'),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],
  cooldown: 3000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: false });

      const { guild, member, user } = interaction;
      if (!guild) {
        await interaction.editReply({
          content: 'Erro: Guild não detectada.',
        });
        return;
      }

      const subcommand = interaction.options.getSubcommand();

      if (subcommand !== 'ver') {
        if (!hasBotAdminPermission(user.id, member)) {
          await interaction.editReply({
            content: `Você não tem permissão para usar este comando. Apenas ${bonfireRoles.adminRoleName} podem usar.`,
          });
          return;
        }
      }

      if (subcommand === 'ver') {
        await handleViewCommand(interaction);
      } else if (subcommand === 'calcular') {
        await handleCalculateCommand(interaction, guild.id);
      } else if (subcommand === 'definir') {
        await handleSetCommand(interaction, guild.id);
      } else if (subcommand === 'priorizar') {
        await handlePrioritizeCommand(interaction, guild.id);
      } else if (subcommand === 'desfazer-prioridade') {
        await handleClearPriorityCommand(interaction, guild.id);
      }
    } catch (error) {
      const message = error instanceof AppError ? error.message : 'Erro desconhecido';
      await interaction.editReply({
        content: `Erro: ${message}`,
      });
    }
  },
};

async function handleViewCommand(interaction: any) {
  const showCurrentUseCase = container.resolve(ShowCurrentDedicatedRankUseCase);
  const currentRank = await showCurrentUseCase.execute({
    guildId: interaction.guildId,
  });

  if (!currentRank) {
    await interaction.editReply({
      content: 'Nenhum ranque dedicado ativo no momento.',
    });
    return;
  }

  const lines: string[] = ['# Ranque Dedicado Atual', ''];
  if (currentRank.isPriorityLocked && currentRank.priorityRankName) {
    lines.push(`Prioridade travada: **${rankWithEmoji(currentRank.priorityRankName)}** fica em 0º lugar (fora da disputa, recompensa máxima) até ser desfeita.`);
    lines.push('');
  }

  for (const rank of currentRank.rankings) {
    lines.push(
      `${rankWithEmoji(`**${rank.rankName}**`)} (${rank.position}º lugar) - +${rank.rewardPerProgression} moedas por progressão (até ${rank.maxTotalReward})`,
    );
  }

  lines.push('');
  if (currentRank.isPriorityLocked) {
    lines.push('Validade: prioridade ativa até o comando desfazer-prioridade ser usado.');
  } else {
    lines.push(`Válido até: <t:${Math.floor(currentRank.validUntil.getTime() / 1000)}:F>`);
  }

  await interaction.editReply({
    content: lines.join('\n'),
  });
}

async function handleCalculateCommand(interaction: any, guildId: string) {
  const questsRepository: any = container.resolve('QuestsRepository');

  const now = nowInBrazil();
  const startDate = nowInBrazil();
  startDate.setDate(startDate.getDate() - 7);

  const quests = await questsRepository.findAllQuestsCreatedInInterval({
    guildId,
    startDate,
    endDate: now,
  });

  const { guild } = interaction;
  const allowedRpgNames = bonfireRpgRankRoles.map((r) => r.name);
  const rpgRankRoleMap = new Map<string, string>(
    guild.roles.cache
      .filter((r: any) => allowedRpgNames.includes(r.name))
      .map((r: any) => [r.id, r.name] as [string, string]),
  );

  const counts = new Map<string, number>();
  for (const rankName of DEDICATED_RANK_VALID_RANKS) {
    counts.set(rankName, 0);
  }

  for (const quest of quests) {
    const questRankNames = new Set<string>();
    for (const roleId of quest.allowedRanks) {
      const rankName = rpgRankRoleMap.get(roleId);
      if (rankName && DEDICATED_RANK_VALID_RANKS.includes(rankName)) {
        questRankNames.add(rankName);
      }
    }
    for (const rankName of questRankNames) {
      counts.set(rankName, (counts.get(rankName) || 0) + 1);
    }
  }

  const rankOrderWithCounts = Array.from(counts.entries())
    .map(([rankName, count]) => ({ rankName, questsCount: count }))
    .sort((a, b) => a.questsCount - b.questsCount);

  const calculateDedicatedRankUseCase = container.resolve(CalculateDedicatedRankUseCase);
  const newRank = await calculateDedicatedRankUseCase.execute({
    guildId,
    rankOrderWithCounts,
    validFrom: now,
  });

  const dedicatedRankChannel = guild.channels.cache.find(
    (ch: any) =>
      ch.type === ChannelType.GuildText &&
      ch.name === '🔰┃ranque-dedicado',
  );
  const channelMention = dedicatedRankChannel ? `<#${dedicatedRankChannel.id}>` : '`🔰┃ranque-dedicado`';

  await publishDedicatedRankToChannel(guild, newRank);

  await interaction.editReply({
    content: `✅ Novo Ranque Dedicado automático calculado e publicado com sucesso no canal ${channelMention}!`,
  });
}

async function handleSetCommand(interaction: any, guildId: string) {
  const orderInput = interaction.options.getString('ordem', true);
  const rankNames = parseRankInput(orderInput, interaction.guild);

  if (new Set(rankNames).size !== rankNames.length) {
    throw new AppError('Não pode haver ranks duplicados na ordem');
  }

  const setDedicatedRankUseCase = container.resolve(SetDedicatedRankManuallyUseCase);
  const newRank = await setDedicatedRankUseCase.execute({
    guildId,
    rankOrder: rankNames,
  });

  const dedicatedRankChannel = interaction.guild.channels.cache.find(
    (ch: any) =>
      ch.type === ChannelType.GuildText &&
      ch.name === '🔰┃ranque-dedicado',
  );
  const channelMention = dedicatedRankChannel ? `<#${dedicatedRankChannel.id}>` : '`🔰┃ranque-dedicado`';

  await publishDedicatedRankToChannel(interaction.guild, newRank);

  await interaction.editReply({
    content: `✅ Ranque Dedicado manual definido e publicado com sucesso no canal ${channelMention}!`,
  });
}

async function handlePrioritizeCommand(interaction: any, guildId: string) {
  const rankInput = interaction.options.getString('rank', true);
  const [priorityRankName] = parseRankInput(rankInput, interaction.guild);

  const setPriorityUseCase = container.resolve(SetDedicatedRankPriorityUseCase);
  const newRank = await setPriorityUseCase.execute({
    guildId,
    priorityRankName,
  });

  const dedicatedRankChannel = interaction.guild.channels.cache.find(
    (ch: any) =>
      ch.type === ChannelType.GuildText &&
      ch.name === '🔰┃ranque-dedicado',
  );
  const channelMention = dedicatedRankChannel ? `<#${dedicatedRankChannel.id}>` : '`🔰┃ranque-dedicado`';

  await publishDedicatedRankToChannel(interaction.guild, newRank);

  await interaction.editReply({
    content: `✅ Prioridade de Ranque Dedicado ativada e publicada com sucesso no canal ${channelMention}!`,
  });
}

async function handleClearPriorityCommand(interaction: any, guildId: string) {
  const clearPriorityUseCase = container.resolve(ClearDedicatedRankPriorityUseCase);
  const updatedRank = await clearPriorityUseCase.execute({ guildId });

  const dedicatedRankChannel = interaction.guild.channels.cache.find(
    (ch: any) =>
      ch.type === ChannelType.GuildText &&
      ch.name === '🔰┃ranque-dedicado',
  );
  const channelMention = dedicatedRankChannel ? `<#${dedicatedRankChannel.id}>` : '`🔰┃ranque-dedicado`';

  await publishDedicatedRankToChannel(interaction.guild, updatedRank);

  await interaction.editReply({
    content: `✅ Prioridade desfeita e ranque atualizado publicado com sucesso no canal ${channelMention}!`,
  });
}

function parseRankInput(input: string, guild: any): string[] {
  const roleIds = getRolesFromMentions(input);

  if (roleIds.length > 0) {
    const allowedRpgNames = bonfireRpgRankRoles.map((r) => r.name);
  const rpgRankRoleMap = new Map<string, string>(
      guild.roles.cache
        .filter((r: any) => allowedRpgNames.includes(r.name))
        .map((r: any) => [r.id, r.name] as [string, string]),
    );

    return roleIds.map((roleId) => {
      const rankName = rpgRankRoleMap.get(roleId);
      if (!rankName || !DEDICATED_RANK_VALID_RANKS.includes(rankName)) {
        throw new AppError(`Cargo inválido: <@&${roleId}>`);
      }
      return rankName as string;
    });
  }

  const rankNames = input
    .split(',')
    .map((rank) => rank.trim())
    .map((rank) => rank.replace(/^@/, '').trim())
    .map((rank) => resolveRankName(rank))
    .filter(Boolean);

  for (const rank of rankNames) {
    if (!DEDICATED_RANK_VALID_RANKS.includes(rank)) {
      throw new AppError(
        `Rank inválido: "${rank}". Ranks válidos: ${DEDICATED_RANK_VALID_RANKS.join(', ')}`,
      );
    }
  }

  return rankNames;
}

function resolveRankName(input: string): string {
  const normalizedInput = normalizeRankName(input);
  const rankName = DEDICATED_RANK_VALID_RANKS.find(
    (rank) =>
      normalizeRankName(rank) === normalizedInput ||
      normalizeRankName(rank.split(' ')[0]) === normalizedInput,
  );

  return rankName || input;
}

function normalizeRankName(input: string): string {
  return input
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

async function publishDedicatedRankToChannel(guild: any, dedicatedRank: any): Promise<void> {
  const dedicatedRankChannel = guild.channels.cache.find(
    (ch: any) =>
      ch.type === ChannelType.GuildText &&
      ch.name === '🔰┃ranque-dedicado',
  );

  if (!dedicatedRankChannel || !dedicatedRankChannel.isTextBased()) {
    throw new AppError('Canal 🔰┃ranque-dedicado não encontrado ou inválido no servidor.');
  }

  const rankMessageLines: string[] = ['# Ranque Dedicado da Semana', ''];

  for (const rank of dedicatedRank.rankings) {
    rankMessageLines.push(
      `${rankWithEmoji(rank.rankName)} – +${rank.rewardPerProgression} moedas por progressão (até o máximo de ${rank.maxTotalReward})`,
    );
  }

  rankMessageLines.push('');
  rankMessageLines.push(`## 🕒 Período de validade:`);
  
  if (dedicatedRank.isPriorityLocked) {
    rankMessageLines.push('Válido até: prioridade ativa até o comando desfazer-prioridade ser usado.');
  } else {
    rankMessageLines.push(
      `De hoje até segunda-feira, ${dedicatedRank.validUntil.toLocaleDateString('pt-BR')}, às 23:59.`,
    );
  }

  const masterMentions = guild.roles.cache
    .filter((r: any) => r.name === bonfireRoles.masterRoleName || r.name === bonfireRoles.testMasterRoleName)
    .map((r: any) => `<@&${r.id}>`)
    .join(' ');

  const message = `${masterMentions}\n\n${rankMessageLines.join('\n')}`;

  await dedicatedRankChannel.send(message);
}

export default command;
