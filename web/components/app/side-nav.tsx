'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { toast } from 'sonner';
import {
  ClockCounterClockwiseIcon,
  HouseIcon,
  SignOutIcon,
  UserIcon,
} from '@phosphor-icons/react/dist/ssr';
import { OwlMascot } from '@/components/app/owl-mascot';
import { useUser } from '@/hooks/useUser';
import { cn } from '@/lib/shadcn/utils';

// App shell navigation for signed-in screens (setup, history). Fixed
// sidebar on desktop, slim top bar on mobile. Session views render
// without it on purpose: a live interview gets the full screen.
export function SideNav() {
  const { user, supabase } = useUser();
  const pathname = usePathname();

  const signOut = async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    toast.info('Signed out.');
  };

  const name = (user?.user_metadata?.full_name as string) || user?.email || '';
  const avatar = user?.user_metadata?.avatar_url as string | undefined;

  const links = [
    { href: '/', label: 'New session', icon: HouseIcon },
    { href: '/history', label: 'History', icon: ClockCounterClockwiseIcon },
    { href: '/profile', label: 'Profile', icon: UserIcon },
  ];

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="border-border/60 bg-card fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r px-4 py-6 md:flex">
        <Link href="/" className="flex items-center gap-2 px-2">
          <OwlMascot size={30} />
          <span className="text-foreground text-sm leading-tight font-semibold">
            Behavioral
            <br />
            Interview Coach
          </span>
        </Link>
        <nav className="mt-8 flex flex-col gap-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                pathname === href
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <Icon className="size-4" weight={pathname === href ? 'bold' : 'regular'} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="border-border/60 mt-auto flex flex-col gap-3 border-t pt-4">
          <div className="flex items-center gap-2.5 px-2">
            {avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatar}
                alt=""
                className="size-8 rounded-full"
                referrerPolicy="no-referrer"
              />
            ) : (
              <span className="bg-primary/15 text-primary flex size-8 items-center justify-center rounded-full text-sm font-semibold">
                {name.slice(0, 1).toUpperCase()}
              </span>
            )}
            <div className="min-w-0">
              <p className="text-foreground truncate text-xs font-medium">{name}</p>
              <p className="text-muted-foreground truncate text-[11px]">{user?.email}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={signOut}
            className="text-muted-foreground hover:bg-muted hover:text-foreground flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors"
          >
            <SignOutIcon className="size-4" />
            Sign out
          </button>
          <p className="text-muted-foreground px-2 font-mono text-[10px] tracking-wider uppercase">
            Built with{' '}
            <a
              target="_blank"
              rel="noopener noreferrer"
              href="https://docs.livekit.io/agents"
              className="underline underline-offset-2"
            >
              LiveKit Agents
            </a>
          </p>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="border-border/60 bg-card fixed inset-x-0 top-0 z-40 flex items-center justify-between border-b px-4 py-2 md:hidden">
        <Link href="/" className="flex items-center gap-2">
          <OwlMascot size={24} />
          <span className="text-foreground text-xs font-semibold">Behavioral Interview Coach</span>
        </Link>
        <div className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-label={label}
              className={cn(
                'rounded-lg p-2',
                pathname === href ? 'text-primary' : 'text-muted-foreground'
              )}
            >
              <Icon className="size-5" weight={pathname === href ? 'bold' : 'regular'} />
            </Link>
          ))}
          <button
            type="button"
            onClick={signOut}
            aria-label="Sign out"
            className="text-muted-foreground rounded-lg p-2"
          >
            <SignOutIcon className="size-5" />
          </button>
        </div>
      </div>
    </>
  );
}
