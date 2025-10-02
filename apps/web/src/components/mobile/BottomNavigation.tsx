/**
 * Bottom navigation bar for mobile interface
 *
 * @component BottomNavigation
 * @since 1.0.0
 */

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

/**
 * Navigation item configuration
 *
 * @interface NavItem
 */
interface NavItem {
  /** Display label for the navigation item */
  label: string;

  /** Route path */
  href: string;

  /** Icon component or emoji */
  icon: string;

  /** Aria label for accessibility */
  ariaLabel: string;
}

/**
 * Props for BottomNavigation component
 *
 * @interface BottomNavigationProps
 */
interface BottomNavigationProps {
  /** Additional CSS classes */
  className?: string;
}

/**
 * Mobile bottom navigation with touch-optimized targets
 *
 * Fixed 60px height with 44px minimum touch targets
 * Highlights active route and supports badge notifications
 *
 * @param {BottomNavigationProps} props - Component props
 * @returns {JSX.Element} Rendered bottom navigation
 *
 * @example
 * ```tsx
 * <BottomNavigation />
 * ```
 */
export const BottomNavigation: React.FC<BottomNavigationProps> = ({
  className = ''
}) => {
  const pathname = usePathname();

  const navItems: NavItem[] = [
    {
      label: 'Home',
      href: '/',
      icon: '🏠',
      ariaLabel: 'Rankings dashboard'
    },
    {
      label: 'Search',
      href: '/search',
      icon: '🔍',
      ariaLabel: 'Prospect discovery'
    },
    {
      label: 'Compare',
      href: '/compare',
      icon: '⚖️',
      ariaLabel: 'Active comparisons'
    },
    {
      label: 'Watch',
      href: '/watchlist',
      icon: '⭐',
      ariaLabel: 'User watchlist'
    },
    {
      label: 'Profile',
      href: '/profile',
      icon: '👤',
      ariaLabel: 'Account and settings'
    }
  ];

  const isActive = (href: string) => {
    if (href === '/') {
      return pathname === '/';
    }
    return pathname.startsWith(href);
  };

  return (
    <nav
      className={`fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50 ${className}`}
      role="navigation"
      aria-label="Mobile navigation"
    >
      <div className="flex justify-around items-center h-[60px] px-2">
        {navItems.map((item) => {
          const active = isActive(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex flex-col items-center justify-center
                min-w-[44px] min-h-[44px] px-2
                transition-colors duration-200
                ${active
                  ? 'text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
                }
              `}
              aria-label={item.ariaLabel}
              aria-current={active ? 'page' : undefined}
            >
              <span className="text-xl mb-1" role="img" aria-hidden="true">
                {item.icon}
              </span>
              <span className="text-xs font-medium">
                {item.label}
              </span>
              {active && (
                <span className="sr-only">Current page</span>
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
};

export default BottomNavigation;