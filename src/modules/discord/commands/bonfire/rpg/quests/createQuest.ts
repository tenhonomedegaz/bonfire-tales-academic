/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { container } from "tsyringe";
import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  GuildMemberRoleManager,
} from "discord.js";
import { SlashCommandBuilder } from "@discordjs/builders";

import { IDiscordCommand } from "@/modules/discord/types";
import {
  getUsersFromMentions,
  getRolesFromMentions,
  isGuildMemberUserId,
} from "@/modules/discord/util";
import { bonfireRoles, bonfireRpgRankRoles } from "@/config/bonfire";
import { CreateQuestUseCase } from "@/modules/rpg/quests/useCases/CreateQuestUseCase";
import { DeleteQuestUseCase } from "@/modules/rpg/quests/useCases/DeleteQuestUseCase";
import { AppError } from "@/shared/errors/AppError";
import { questInfoEmbedMessage } from "./questEmbeds";

const commandData = new SlashCommandBuilder()
  .setName("missao-criar")
  .setDescription("📜 Cria uma missão")
  .addStringOption((o) =>
    o.setName("nome-missao").setDescription("Nome da Missão").setRequired(true)
  )
  .addStringOption((o) =>
    o.setName("descricao-missao").setDescription("Descrição da Missão").setRequired(true)
  )
  .addStringOption((o) =>
    o.setName("data-missao").setDescription("Data dd/mm/aaaa").setRequired(true)
  )
  .addStringOption((o) =>
    o.setName("hora-missao").setDescription("Hora hh:mm").setRequired(true)
  )
  .addNumberOption((o) =>
    o
      .setName("quantidade-participantes")
      .setDescription("Quantidade de participantes")
      .setRequired(true)
  )
  .addStringOption((o) =>
    o
      .setName("ranks")
      .setDescription("Selecione os ranks permitidos @rank1 @rank2")
      .setRequired(true)
  )
  .addStringOption((o) =>
    o
      .setName("link-mesa")
      .setDescription("Link da mesa da missão")
      .setRequired(true)
  )
  .addStringOption((o) => o.setName("tipo-missao").setDescription("Tipo").setRequired(false))
  .addStringOption((o) =>
    o.setName("link-regras").setDescription("Link com regras").setRequired(false)
  )
  .addStringOption((o) =>
    o.setName("tags-missao").setDescription("tag1, tag2").setRequired(false)
  )
  .addStringOption((o) =>
    o
      .setName("jogadores-prioritarios")
      .setDescription("Jogadores prioritarios")
      .setRequired(false)
  );
  
const mandatoryPlayersOption = (o: any) =>
  o
    .setName("jogadores-obrigatorios")
    .setDescription("Jogadores obrigatorios")
    .setRequired(false);

commandData.addStringOption(mandatoryPlayersOption);

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.masterRoleName, bonfireRoles.testMasterRoleName],
  cooldown: 3000,

  async execute(bot, interaction) {
    try {
      await interaction.reply({ content: "Criando Missão...", ephemeral: true });

      const { user, guild } = interaction;

      if (!guild) {
        await interaction.followUp({ content: "Erro: guild não detectada.", ephemeral: true });
        return;
      }

      if (!interaction.channel?.isTextBased()) {
        await interaction.followUp({
          content: "Este comando só pode ser usado em canais de texto.",
          ephemeral: true,
        });
        return;
      }

      const questName = interaction.options.getString("nome-missao", true);
      const questDescription = interaction.options.getString("descricao-missao", true);
      const questDateString = interaction.options.getString("data-missao", true);
      const questTimeString = interaction.options.getString("hora-missao", true);
      const playersAmount = interaction.options.getNumber("quantidade-participantes", true);
      const questTableUrl = interaction.options.getString("link-mesa", true);

      const questRules = interaction.options.getString("link-regras") || "https://app.roll20.net";
      const questTags = interaction.options.getString("tags-missao") || "";
      const questType = interaction.options.getString("tipo-missao") || "-";

      const priorityPlayersMentions =
        interaction.options.getString("jogadores-prioritarios") || "";

      const mandatoryPlayersMentions =
        interaction.options.getString("jogadores-obrigatorios") || "";

      const createdByUserId = user.id;

      const highPriorityPlayersUsersIds = getUsersFromMentions(priorityPlayersMentions);
      const mandatoryPlayersUsersIds = getUsersFromMentions(mandatoryPlayersMentions);

      for (const p of mandatoryPlayersUsersIds) {
        if (!isGuildMemberUserId(p, guild)) {
          await interaction.followUp({
            content: `Usuário inválido: <@${p}>`,
            ephemeral: true,
          });
          return;
        }
      }

      for (const p of highPriorityPlayersUsersIds) {
        if (!isGuildMemberUserId(p, guild)) {
          await interaction.followUp({
            content: `Usuário inválido: <@${p}>`,
            ephemeral: true,
          });
          return;
        }
      }

      const uniqueMandatoryPlayers = [...new Set(mandatoryPlayersUsersIds)];
      const uniquePriorityPlayers = highPriorityPlayersUsersIds.filter(
        (id) => !uniqueMandatoryPlayers.includes(id)
      );

      const allowedRolesMentions = interaction.options.getString("ranks", true);
      const allowedQuestRolesIds = getRolesFromMentions(allowedRolesMentions);

      const allowedRpgNames = bonfireRpgRankRoles.map((r) => r.name);
      const rpgRankRoleIds = guild.roles.cache
        .filter((r) => allowedRpgNames.includes(r.name))
        .map((r) => r.id);

      for (const r of allowedQuestRolesIds) {
        if (!rpgRankRoleIds.includes(r)) {
          await interaction.followUp({
            content: `Cargo inválido: <@&${r}>`,
            ephemeral: true,
          });
          return;
        }
      }

      const createQuestUseCase = container.resolve(CreateQuestUseCase);

      const createdQuest = await createQuestUseCase.execute({
        guildId: guild.id,
        name: questName,
        description: questDescription,
        questDate: questDateString,
        questTime: questTimeString,
        playersAmount,
        rules: questRules,
        tags: questTags.split(",").map((t) => t.trim()),
        type: questType,
        tableUrl: questTableUrl,
        questMaster: user.id,
        mandatoryPlayers: uniqueMandatoryPlayers,
        highPriorityPlayers: uniquePriorityPlayers,
        allowedRanks: allowedQuestRolesIds,
        createdBy: createdByUserId,
        scheduler: bot.scheduler,
        requestedAt: interaction.createdAt,
      });

      const questInfoMessage = await questInfoEmbedMessage({ quest: createdQuest });

      const deleteCustomId = `delete-quest:${createdQuest.id}`;

      const deleteRow = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
          .setCustomId(deleteCustomId)
          .setLabel("CANCELAR E EXCLUIR MISSÃO")
          .setStyle(ButtonStyle.Danger)
      );

      const channelLink = createdQuest.channelId ? ` no canal <#${createdQuest.channelId}>` : "";

      await interaction.followUp({
        content: `Missão criada com sucesso${channelLink}!`,
        embeds: [questInfoMessage],
        components: [deleteRow],
        ephemeral: true,
      });

    } catch (error) {
      bot.logger.log("error", `Erro no comando ${commandData.name}`, error);
      if (error instanceof AppError) {
        await interaction.followUp({ content: `Erro: ${error.message}`, ephemeral: true }).catch(() => {});
      } else {
        await interaction.followUp({ content: "Erro: Ocorreu um erro inesperado ao tentar criar a missão.", ephemeral: true }).catch(() => {});
      }
    }
  },
};

export default command;
