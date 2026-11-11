import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { bonfireRoles } from '@/config/bonfire';
import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { hasBotAdminPermission } from '@/modules/discord/util';
import { updateQuestEmbeds } from './updateQuestEmbeds';

const objectIdRegex = /^(?:[a-f\d]{24}|c[a-z0-9]{24})$/i;

async function resolveQuestFromInput(input: string): Promise<Quest | null> {
  if (objectIdRegex.test(input)) {
    const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
    return showQuestByIdUseCase.execute(input);
  }

  const showPublishedQuestsUseCase = container.resolve(ShowPublishedQuestsUseCase);
  const quests = await showPublishedQuestsUseCase.execute({
    searchTerm: input,
    limit: 25,
  });

  const normalizedInput = input.trim().toLowerCase();

  return (
    quests.find((quest) => quest.name.toLowerCase() === normalizedInput) ||
    quests.find((quest) => quest.name.toLowerCase().includes(normalizedInput)) ||
    null
  );
}

function parseTags(input: string): string[] {
  return input
    .split(',')
    .map((tag) => tag.trim())
    .filter((tag) => tag.length > 0);
}

// Remove duplicatas ignorando maiúsculas/minúsculas, preservando a primeira grafia.
function dedupeTags(tags: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const tag of tags) {
    const key = tag.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      result.push(tag);
    }
  }
  return result;
}

const updateQuestTagsCommandData = new SlashCommandBuilder()
  .setName('missao-tags')
  .setDescription('Edita as tags de uma missão (ex: adicionar a tag EVENTO).')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Selecione a missão').setAutocomplete(true).setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('tags').setDescription('Tags separadas por vírgula (ex: evento, oficial)').setRequired(true),
  )
  .addStringOption((option) =>
    option
      .setName('modo')
      .setDescription('Como aplicar as tags (padrão: definir)')
      .setRequired(false)
      .addChoices(
        { name: 'Definir (substitui todas as tags)', value: 'definir' },
        { name: 'Adicionar (mantém as existentes)', value: 'adicionar' },
        { name: 'Remover', value: 'remover' },
      ),
  );

const updateQuestTagsCommand: IDiscordCommand = {
  commandData: updateQuestTagsCommandData,
  allowedRoles: [
    bonfireRoles.masterRoleName,
    bonfireRoles.testMasterRoleName,
    bonfireRoles.adminRoleName,
    bonfireRoles.moderatorRoleName,
  ],
  cooldown: 5 * 1000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      const { user, guild } = interaction;

      if (!guild) {
        await interaction.followUp({ content: 'Não foi possível detectar o servidor.', flags: [MessageFlags.Ephemeral] });
        return;
      }

      const questInput = interaction.options.getString('missao', true);
      const quest = await resolveQuestFromInput(questInput);

      if (!quest) {
        await interaction.followUp({
          content: 'Missão não localizada. Selecione pelo autocomplete.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const requesterIsQuestMaster = user.id === quest.questMaster;
      const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
      const requesterIsAdminOrMod =
        memberRoles.includes(bonfireRoles.adminRoleName) ||
        memberRoles.includes(bonfireRoles.moderatorRoleName) ||
        hasBotAdminPermission(user.id, interaction.member);

      if (!requesterIsQuestMaster && !requesterIsAdminOrMod) {
        await interaction.followUp({
          content: 'Apenas o mestre da missão ou a Staff podem editar as tags.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const tagsInput = interaction.options.getString('tags', true);
      const mode = interaction.options.getString('modo') ?? 'definir';
      const inputTags = parseTags(tagsInput);

      if (inputTags.length === 0) {
        await interaction.followUp({
          content: 'Nenhuma tag válida informada. Use tags separadas por vírgula (ex: `evento, oficial`).',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const previousTags = quest.tags ?? [];
      let newTags: string[];

      if (mode === 'adicionar') {
        newTags = dedupeTags([...previousTags, ...inputTags]);
      } else if (mode === 'remover') {
        const toRemove = new Set(inputTags.map((tag) => tag.toLowerCase()));
        newTags = previousTags.filter((tag) => !toRemove.has(tag.toLowerCase()));
      } else {
        newTags = dedupeTags(inputTags);
      }

      quest.tags = newTags;

      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
      await updateQuestUseCase.execute(quest);

      // Atualiza o embed público da missão para refletir as novas tags.
      if (quest.isPublished) {
        await updateQuestEmbeds(bot, guild, quest.id).catch(() => null);
      }

      const beforeText = previousTags.length ? previousTags.join(', ') : '(nenhuma)';
      const afterText = newTags.length ? newTags.join(', ') : '(nenhuma)';
      const wasEvent = previousTags.some((tag) => tag.toLowerCase() === 'evento');
      const isEventNow = newTags.some((tag) => tag.toLowerCase() === 'evento');

      let eventNote = '';
      if (isEventNow && !wasEvent) {
        eventNote = '\n\n🔥 Esta missão agora conta como **missão de evento** (recompensas de evento ativadas ao finalizar).';
      } else if (!isEventNow && wasEvent) {
        eventNote = '\n\n⚠️ A tag **evento** foi removida — a missão deixou de contar como missão de evento.';
      }

      await interaction.followUp({
        content:
          `Tags da missão **${quest.name}** atualizadas.\n` +
          `Antes: ${beforeText}\n` +
          `Agora: ${afterText}` +
          eventNote,
        flags: [MessageFlags.Ephemeral],
      });
    } catch (error) {
      bot.logger.log('error', 'Erro no comando missao-tags', error);
      await interaction.followUp({
        content: `Erro ao editar as tags: ${error}`,
        flags: [MessageFlags.Ephemeral],
      }).catch(() => null);
    }
  },
};

export default updateQuestTagsCommand;
