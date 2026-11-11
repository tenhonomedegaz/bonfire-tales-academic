import addPayment from './admin/addPayment';
import validateSubscribers from './admin/validateSubscribers';
import addToken from './admin/addToken';
import removeToken from './admin/removeToken';
import desligar from './admin/desligar';
import gitUpdate from './admin/gitUpdate';
import gitForceUpdate from './admin/gitForceUpdate';
import consoleCommand from './admin/console';
import registerLog from './admin/registerLog';

import rewardUpdate from './admin/rewardUpdate';
import verLogs from './admin/verLogs';
import removerLogJogador from './admin/removerLogJogador';
import siteCommand from './admin/site';
import verAgendamentos from './admin/verAgendamentos';

import atlas from './atlas';
import helpCommand from './help';

import showActiveTransactions from './subscription/showActiveTransactions';
import showTokens from './subscription/showTokens';
import useToken from './subscription/useToken';
import validateSubscription from './subscription/validateSubscription';
import subscriptionInfo from './subscription/subscriptionInfo';

import createQuest from './rpg/quests/createQuest';
import createPrivateQuest from './rpg/quests/createPrivateQuest';
import deleteQuest from './rpg/quests/deleteQuest';
import pickQuestPlayers from './rpg/quests/pickQuestPlayers';
import rescheduleQuest from './rpg/quests/rescheduleQuest';
import controlQuest, {
  addQuestPlayersCommand,
  dropQuestPlayerCommand,
  questQueueCommand,
} from './rpg/quests/controlQuest';
import updateQuestTimeCommand from './rpg/quests/updateQuestTime';
import updateQuestRankCommand from './rpg/quests/updateQuestRank';
import updateQuestTagsCommand from './rpg/quests/updateQuestTags';
import rankDedicado from './rpg/rankDedicado';
import meusLogs from './rpg/meus-logs';
import updateLogs from './rpg/updateLogs';
import removerLog from './rpg/removerLog';
import missaoLevantamento from './rpg/quests/missaoLevantamento';

export const bonfireCommands = [
  // ADMIN
  addPayment,
  validateSubscribers,
  addToken,
  removeToken,
  desligar,
  gitUpdate,
  gitForceUpdate,
  consoleCommand,
  registerLog,

  rewardUpdate,
  verLogs,
  removerLogJogador,
  siteCommand,
  verAgendamentos,

  atlas,
  helpCommand,

  // SUBSCRIPTION
  showActiveTransactions,
  showTokens,
  useToken,
  validateSubscription,
  subscriptionInfo,

  // QUESTS
  createQuest,
  createPrivateQuest,
  deleteQuest,
  rescheduleQuest,
  controlQuest,
  pickQuestPlayers,
  questQueueCommand,
  addQuestPlayersCommand,
  dropQuestPlayerCommand,
  updateQuestTimeCommand,
  updateQuestRankCommand,
  updateQuestTagsCommand,
  rankDedicado,
  meusLogs,
  updateLogs,
  removerLog,
  missaoLevantamento,
];
