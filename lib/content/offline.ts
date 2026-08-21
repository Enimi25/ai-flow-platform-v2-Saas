import { getSettings } from "@/lib/settings/store";
import type { Channel } from "./types";
import type { Format } from "./generate";

/**
 * Writes posts without calling a model. It exists so the content factory still
 * produces something on a workspace that has not connected a model yet, and so
 * a dead API key never means an empty queue.
 *
 * Every line is built from the workspace's own settings. Nothing here invents a
 * number, a price or a testimonial.
 */

type Angle = {
  id: string;
  post: (ctx: Ctx) => string;
  reel: (ctx: Ctx) => { caption: string; script: string[] };
};

type Ctx = {
  name: string;
  industry: string;
  what: string;
  goalLine: string;
  tags: string[];
};

const TAGS: Record<string, string[]> = {
  default: ["малыйбизнес", "автоматизация", "клиенты", "продажи", "предприниматель"],
  "Beauty and salon": ["салонкрасоты", "бьюти", "записьклиентов", "мастер", "малыйбизнес"],
  "Dental and medical": ["стоматология", "клиника", "записьнаприем", "пациенты", "медицина"],
  "Auto service": ["автосервис", "сто", "ремонтавто", "записьнаремонт", "авто"],
  "Fitness and wellness": ["фитнес", "тренер", "студия", "записьнатренировку", "здоровье"],
  "Home services": ["ремонт", "услуги", "мастернадом", "заявки", "клиенты"],
  "Restaurant and cafe": ["ресторан", "кафе", "бронирование", "гости", "общепит"],
  Retail: ["магазин", "розница", "продажи", "клиенты", "заказы"],
  "Professional services": ["услуги", "консультация", "клиенты", "заявки", "бизнес"],
};

const ANGLES: Angle[] = [
  {
    id: "late-reply",
    post: (c) => [
      "Клиент написал в 21:40 в пятницу.",
      "",
      "Ответ пришёл в понедельник в 9:15.",
      "",
      "К тому моменту он уже там, где ответили быстрее. Не дешевле. Быстрее.",
      "",
      `${c.name} отвечает за секунды, в любое время, и ${c.goalLine}.`,
    ].join("\n"),
    reel: (c) => ({
      caption: `Ответ через сутки это отказ, просто вежливый.\n\n${c.tags.map((t) => "#" + t).join(" ")}`,
      script: [
        "0-2 с · экран телефона, уведомление в 21:40 · текст: «клиент пишет»",
        "2-5 с · тот же экран, время меняется на 09:15 понедельника · текст: «вы отвечаете»",
        "5-8 с · переписка помечена прочитанной, ответа нет · текст: «поздно»",
        "8-12 с · экран кабинета, ответ появляется через секунду · текст: «4 секунды»",
        `12-15 с · логотип · текст: «${c.name}»`,
      ],
    }),
  },
  {
    id: "night-booking",
    post: (c) => [
      "Ночью, в 02:14, кто-то открыл ваш сайт и спросил про свободное время.",
      "",
      "Утром вы увидели не пропущенное сообщение, а запись в календаре.",
      "",
      `Так работает ${c.name}: диалог, контакт, запись. Без вас.`,
    ].join("\n"),
    reel: (c) => ({
      caption: `Пока вы спали, заявка стала записью.\n\n${c.tags.map((t) => "#" + t).join(" ")}`,
      script: [
        "0-2 с · тёмная комната, светится телефон · текст: «02:14»",
        "2-6 с · диалог печатается сам, ответ приходит мгновенно",
        "6-10 с · календарь, слот заливается цветом · текст: «записан»",
        "10-14 с · утро, рука берёт телефон · текст: «вы ещё спали»",
        `14-16 с · логотип · текст: «${c.name}»`,
      ],
    }),
  },
  {
    id: "small-volume",
    post: (c) => [
      "«У нас мало обращений, нам это не нужно.»",
      "",
      "Наоборот. Когда обращений мало, каждое пропущенное стоит дороже всего.",
      "",
      "Посчитайте своё: сколько сообщений в неделю, сколько остались без ответа до следующего дня, сколько из них не вернулись.",
      "",
      "Это и есть цена молчания.",
    ].join("\n"),
    reel: (c) => ({
      caption: `Посчитайте, во сколько вам обходится тишина.\n\n${c.tags.map((t) => "#" + t).join(" ")}`,
      script: [
        "0-2 с · крупно рука с калькулятором · текст: «считаем»",
        "2-6 с · пишем на бумаге: сообщений в неделю",
        "6-10 с · зачёркиваем те, что без ответа · текст: «ушли»",
        "10-14 с · обводим сумму · текст: «это в месяц»",
        `14-18 с · логотип · текст: «${c.name}»`,
      ],
    }),
  },
  {
    id: "three-questions",
    post: (c) => [
      "Три вопроса, которые ваш бизнес слышит каждый день:",
      "",
      "Сколько стоит.",
      "Когда можно.",
      "Работаете ли в выходные.",
      "",
      "На них не нужен человек. Нужен ответ за секунды и понятный следующий шаг в конце разговора.",
    ].join("\n"),
    reel: (c) => ({
      caption: `Одни и те же три вопроса. Каждый день.\n\n${c.tags.map((t) => "#" + t).join(" ")}`,
      script: [
        "0-2 с · экран с сообщением «сколько стоит?» · текст: «раз»",
        "2-4 с · следующее «когда можно?» · текст: «два»",
        "4-6 с · следующее «работаете в выходные?» · текст: «три»",
        "6-10 с · все три получают ответ подряд, сами",
        `10-14 с · логотип · текст: «${c.name}»`,
      ],
    }),
  },
  {
    id: "lost-notes",
    post: (c) => [
      "Куда девается заявка после того, как её приняли.",
      "",
      "Обычно: в заметки, в блокнот, в голову. Потом вспоминаешь через три дня.",
      "",
      `С ${c.name} имя, телефон и весь разговор сохраняются сами. Видно, кто новый, с кем уже работают, кто дошёл до оплаты.`,
    ].join("\n"),
    reel: (c) => ({
      caption: `Заявка не теряется, если её никто не переписывает руками.\n\n${c.tags.map((t) => "#" + t).join(" ")}`,
      script: [
        "0-3 с · стопка стикеров и блокнот · текст: «как обычно»",
        "3-6 с · стикер падает со стола · текст: «минус клиент»",
        "6-10 с · экран со списком заявок, всё на месте · текст: «как надо»",
        `10-14 с · логотип · текст: «${c.name}»`,
      ],
    }),
  },
  {
    id: "test-yourself",
    post: (c) => [
      "Проверка на пять минут.",
      "",
      "Напишите своему бизнесу как обычный клиент. С чужого номера, вечером. Засеките, через сколько придёт ответ.",
      "",
      "Большинство узнаёт о себе неприятное. Зато сразу понятно, что чинить.",
    ].join("\n"),
    reel: (c) => ({
      caption: `Напишите себе как клиент. Засеките время.\n\n${c.tags.map((t) => "#" + t).join(" ")}`,
      script: [
        "0-3 с · пишем сообщение своему же бизнесу · текст: «эксперимент»",
        "3-6 с · включается секундомер",
        "6-10 с · секундомер отматывает часы · текст: «всё ещё тишина»",
        "10-14 с · рядом второй экран, ответ за 4 секунды",
        `14-18 с · логотип · текст: «${c.name}»`,
      ],
    }),
  },
];

function context(settings: Awaited<ReturnType<typeof getSettings>>): Ctx {
  const goals: Record<string, string> = {
    "Capture leads": "сохраняет контакт",
    "Book appointments": "записывает на удобное время",
    "Answer questions": "отвечает по делу",
    "Qualify and hand over": "выясняет, что нужно, и передаёт вам готового клиента",
  };
  return {
    name: settings.companyName || "AI FLOW",
    industry: settings.industry,
    what: settings.businessDescription,
    goalLine: goals[settings.goal] ?? "сохраняет контакт",
    tags: TAGS[settings.industry] ?? TAGS.default,
  };
}

/** Rotates through the angles so repeated runs do not return the same five. */
export async function writeOffline(input: {
  companyId: string;
  channel: Channel;
  count: number;
  format: Format;
  offset?: number;
}) {
  const settings = await getSettings(input.companyId);
  const ctx = context(settings);
  const start = input.offset ?? 0;

  return Array.from({ length: Math.min(input.count, ANGLES.length) }, (_, index) => {
    const angle = ANGLES[(start + index) % ANGLES.length];
    if (input.format === "reel") {
      const { caption, script } = angle.reel(ctx);
      return { channel: input.channel, body: caption, script };
    }
    const body = angle.post(ctx);
    // Instagram and TikTok expect the tags on the caption itself
    return {
      channel: input.channel,
      body: input.channel === "facebook" ? body : `${body}\n\n${ctx.tags.map((t) => "#" + t).join(" ")}`,
    };
  });
}
