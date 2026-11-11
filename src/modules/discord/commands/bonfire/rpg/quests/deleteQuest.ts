import { container } from "tsyringe";
import { SlashCommandBuilder } from "@discordjs/builders";
import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  GuildMemberRoleManager,
} from "discord.js";

import { IDiscordCommand } from "@/modules/discord/types";
import { bonfireRoles } from "@/config/bonfire";
import { DeleteQuestUseCase } from "@/modules/rpg/quests/useCases/DeleteQuestUseCase";
import { ShowQuestByIdUseCase } from "@/modules/rpg/quests/useCases/ShowQuestByIdUseCase";
import { AppError } from "@/shared/errors/AppError";
import { questInfoEmbedMessage } from "./questEmbeds";
import { hasBotAdminPermission } from "@/modules/discord/util";

const commandData = new SlashCommandBuilder()
  .setName("missao-excluir")
  .setDescription("📜 Exclui uma missão que você criou")
  .addStringOption((o) =>
    o.setName("missao").setDescription("Missão").setAutocomplete(true).setRequired(true)
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.masterRoleName, bonfireRoles.testMasterRoleName],
  cooldown: 3000,

  async execute(bot, interaction) {
    try {
      await interaction.reply({ content: "Carregando missão...", ephemeral: true });

      const { user, guild } = interaction;

      if (!guild) {
        await interaction.followUp({ content: "Erro: guild não detectada.", ephemeral: true });
        return;
      }

      const questId = interaction.options.getString("missao", true);

      const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
      const quest = await showQuestByIdUseCase.execute(questId);

      if (!quest) {
        await interaction.followUp({ content: "Missão não encontrada.", ephemeral: true });
        return;
      }

      const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
      const requesterIsAdmin =
        memberRoles.includes(bonfireRoles.adminRoleName) ||
        hasBotAdminPermission(user.id, interaction.member);

      if (!requesterIsAdmin && quest.createdBy !== user.id) {
        await interaction.followUp({ content: "Você não tem permissão para excluir essa missão.", ephemeral: true });
        return;
      }

      const showQueueList = requesterIsAdmin || user.id === quest.questMaster;

      const questInfoMessage = await questInfoEmbedMessage({
        quest,
        showQueueList,
      });

      const deleteCustomId = `delete-quest:${quest.id}`;

      const deleteRow = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
          .setCustomId(deleteCustomId)
          .setLabel("CANCELAR E EXCLUIR MISSÃO")
          .setStyle(ButtonStyle.Danger)
      );

      await interaction.followUp({
        content: "Confirmação:",
        embeds: [questInfoMessage],
        components: [deleteRow],
        ephemeral: true,
      });

    } catch (error) {
      bot.logger.log("error", `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
