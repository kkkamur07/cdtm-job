import AppShell from "@/components/AppShell";
import { getIdentity } from "@/auth/session";
import { loadMe, loadMyMember, loadUnreadCount } from "@/api/server";

/**
 * Everything except /login renders inside the shell.
 *
 * The three reads here are independent, so they go out together: the header
 * must not become a waterfall in front of every page. The Member read is what
 * puts a person's own name in the corner rather than their e-mail; it fails
 * quietly for an account that has not been matched to a roster entry.
 *
 * The badge reads a count endpoint rather than the announcements list. The list
 * is fifty announcements with their bodies, and the shell renders on every
 * route; the pages that show announcements still load it themselves.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
    const { accessToken } = await getIdentity();

    const [me, member, unread] = accessToken
        ? await Promise.all([
              loadMe().catch(() => null),
              loadMyMember().catch(() => null),
              loadUnreadCount().catch(() => null),
          ])
        : [null, null, null];

    return (
        <AppShell
            signedIn={Boolean(accessToken)}
            name={member?.name ?? me?.account.full_name ?? me?.account.email ?? null}
            avatarUrl={member?.avatar?.sm ?? me?.account.avatar_url ?? null}
            unread={unread?.unread ?? 0}
        >
            {children}
        </AppShell>
    );
}
