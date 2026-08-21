import Link from "next/link";
import s from "./data-deletion.module.css";

export const metadata = {
  title: "Data deletion | AI FLOW",
  description: "How to have everything AI FLOW holds about you erased.",
};

export default async function DataDeletionPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const { id } = await searchParams;

  return (
    <main className={s.page}>
      <div className={s.inner}>
        <Link href="/" className={s.brand}>
          <span>AI</span> AI FLOW
        </Link>

        <h1 className="h1">Your data has been deleted.</h1>

        {id ? (
          <>
            <p className="body">
              Everything we held that came from your account has been removed: the messages you
              exchanged with the assistant, any contact details you gave it, and any appointment
              it made for you. Nothing was kept behind a flag — the records are gone.
            </p>
            <p className={s.code}>
              Confirmation code<b>{id}</b>
            </p>
          </>
        ) : (
          <p className="body">
            This page confirms a deletion request. If you arrived here from Facebook or Instagram
            after removing AI FLOW, your records have already been erased.
          </p>
        )}

        <h2 className={s.h2}>If you want to ask for deletion yourself</h2>
        <p className="body">
          Write to <a href="mailto:baskinltd@yahoo.com">baskinltd@yahoo.com</a> from the address
          you used, or from the account you messaged us on. We erase everything within 30 days and
          write back to say it is done. You do not have to give a reason.
        </p>

        <h2 className={s.h2}>What we hold in the first place</h2>
        <ul className={s.list}>
          <li>The messages you sent the assistant and its replies.</li>
          <li>Contact details you chose to give it, such as a phone number or an email.</li>
          <li>Which channel you wrote from, and when.</li>
          <li>Any appointment the assistant booked for you.</li>
        </ul>
        <p className={s.note}>
          We do not sell any of it, we do not use it for advertising, and no business can see
          anything except the conversations that came to their own account.
        </p>

        <p className={s.back}>
          <Link href="/privacy">Read the full privacy notice</Link>
        </p>
      </div>
    </main>
  );
}
