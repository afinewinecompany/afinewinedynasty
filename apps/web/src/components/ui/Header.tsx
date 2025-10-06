'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, User, Zap, Menu, Wine, Brain } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from './button';

const Header: React.FC = () => {
  const pathname = usePathname();
  const { user } = useAuth();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  const isActive = (path: string) => pathname === path;

  const navLinks = [
    { href: '/', label: 'Dashboard' },
    { href: '/prospects', label: 'Prospects' },
    { href: '/ml-predictions', label: 'ML Predictions' },
    { href: '/discovery', label: 'Tools' },
    { href: '/account/subscription', label: 'Account' },
  ];

  return (
    <header className="bg-card/95 backdrop-blur-sm border-b border-border sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center gap-2 group">
              <Wine className="w-6 h-6 text-wine-rose group-hover:text-wine-periwinkle transition-colors" />
              <span className="font-display text-xl md:text-2xl font-semibold tracking-tight bg-gradient-to-r from-wine-rose via-wine-periwinkle to-wine-cyan bg-clip-text text-transparent group-hover:from-wine-periwinkle group-hover:via-wine-cyan group-hover:to-wine-mint transition-all duration-300">
                A Fine Wine Dynasty
              </span>
            </Link>
          </div>

          {/* Desktop Navigation - Center */}
          <nav className="hidden md:flex items-center space-x-8">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-all relative flex items-center gap-1.5 ${
                  isActive(link.href)
                    ? 'text-wine-periwinkle after:absolute after:bottom-[-20px] after:left-0 after:right-0 after:h-0.5 after:bg-wine-periwinkle'
                    : 'text-foreground/80 hover:text-wine-rose'
                }`}
              >
                {link.href === '/ml-predictions' && <Brain className="w-4 h-4" />}
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Right Side Actions */}
          <div className="flex items-center gap-3">
            {/* Search Icon */}
            <button className="p-2 text-muted-foreground hover:text-accent transition-colors hidden md:block">
              <Search className="w-5 h-5" />
            </button>

            {user ? (
              <>
                {/* Profile */}
                <Link
                  href="/account/subscription"
                  className="p-2 text-muted-foreground hover:text-accent transition-colors"
                >
                  <User className="w-5 h-5" />
                </Link>

                {/* Upgrade Button (if not premium) */}
                {user.subscriptionTier !== 'premium' && (
                  <Link href="/subscription">
                    <Button
                      variant="default"
                      size="sm"
                      className="hidden md:flex items-center gap-2 bg-gradient-to-r from-wine-rose to-wine-periwinkle hover:from-wine-deep hover:to-wine-rose text-white shadow-md hover:shadow-lg transition-all"
                    >
                      <Zap className="w-4 h-4" />
                      Upgrade
                    </Button>
                  </Link>
                )}
              </>
            ) : (
              /* Sign In Button for unauthenticated users */
              <Link href="/login">
                <Button
                  variant="default"
                  size="sm"
                  className="hidden md:flex items-center gap-2 bg-gradient-to-r from-wine-rose to-wine-periwinkle hover:from-wine-deep hover:to-wine-rose text-white shadow-md hover:shadow-lg transition-all"
                >
                  <User className="w-4 h-4" />
                  Sign In
                </Button>
              </Link>
            )}

            {/* Mobile Menu Button */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="md:hidden p-2 text-muted-foreground hover:text-accent transition-colors"
            >
              <Menu className="w-6 h-6" />
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-border bg-card/95 backdrop-blur-sm">
          <div className="px-4 py-3 space-y-2">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center gap-2 px-3 py-2 rounded-md text-base font-medium transition-colors ${
                  isActive(link.href)
                    ? 'bg-accent/20 text-accent'
                    : 'text-foreground/80 hover:bg-muted'
                }`}
              >
                {link.href === '/ml-predictions' && <Brain className="w-4 h-4" />}
                {link.label}
              </Link>
            ))}
            {user ? (
              user.subscriptionTier !== 'premium' && (
                <Link href="/subscription" onClick={() => setIsMobileMenuOpen(false)}>
                  <Button
                    variant="default"
                    className="w-full mt-2 bg-gradient-to-r from-wine-rose to-wine-periwinkle hover:from-wine-deep hover:to-wine-rose text-white shadow-md"
                  >
                    <Zap className="w-4 h-4 mr-2" />
                    Upgrade to Premium
                  </Button>
                </Link>
              )
            ) : (
              <Link href="/login" onClick={() => setIsMobileMenuOpen(false)}>
                <Button
                  variant="default"
                  className="w-full mt-2 bg-gradient-to-r from-wine-rose to-wine-periwinkle hover:from-wine-deep hover:to-wine-rose text-white shadow-md"
                >
                  <User className="w-4 h-4 mr-2" />
                  Sign In
                </Button>
              </Link>
            )}
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
