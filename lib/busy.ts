import { answerLanguage } from "@/lib/language";

/**
 * What the customer hears when every model is rate limited.
 *
 * The old line was "I cannot reach my brain right now", in English, with a 503.
 * On a salon's website that reads as broken software, and the visitor leaves.
 *
 * A person whose colleague is busy does not announce a system failure. They say
 * someone will come back, and they take a number. That is a worse answer than
 * the agent would have given and a much better one than an error, and it still
 * captures the lead — which is the only thing that mattered about the message.
 */
const BUSY: Record<string, string> = {
  Russian:
    "Секунду, у меня сейчас много обращений. Оставьте телефон или email, и мы вернёмся к вам буквально через несколько минут.",
  "Russian, written in Cyrillic":
    "Секунду, у меня сейчас много обращений. Оставьте телефон или email, и мы вернёмся к вам буквально через несколько минут.",
  Spanish:
    "Un momento, tengo muchas consultas ahora mismo. Déjeme su teléfono o correo y le respondemos en unos minutos.",
  French:
    "Un instant, beaucoup de demandes en ce moment. Laissez votre téléphone ou votre e-mail et nous revenons vers vous dans quelques minutes.",
  German:
    "Einen Moment, gerade sehr viele Anfragen. Hinterlassen Sie Telefon oder E-Mail, wir melden uns in wenigen Minuten.",
  Italian:
    "Un attimo, in questo momento ho molte richieste. Mi lasci un telefono o una email e le rispondiamo tra pochi minuti.",
  English:
    "One moment, there are a lot of messages coming in right now. Leave a phone number or an email and we will come back to you in a few minutes.",
};

export function busyReply(customerMessage: string) {
  return BUSY[answerLanguage(customerMessage)] ?? BUSY.English;
}
