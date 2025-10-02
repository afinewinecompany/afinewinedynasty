'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/hooks/use-toast';
import {
  Share2,
  Twitter,
  Linkedin,
  Copy,
  ExternalLink,
  Check,
} from 'lucide-react';

interface SocialShareProps {
  url: string;
  title: string;
  description?: string;
  hashtags?: string[];
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

interface ShareData {
  url: string;
  title: string;
  text?: string;
}

export function SocialShare({
  url,
  title,
  description,
  hashtags = [],
  className = '',
  size = 'md',
}: SocialShareProps) {
  const [copied, setCopied] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  // Ensure URL is absolute
  const shareUrl = url.startsWith('http')
    ? url
    : `${window.location.origin}${url}`;

  const shareText = description || title;
  const hashtagString =
    hashtags.length > 0 ? hashtags.map((tag) => `#${tag}`).join(' ') : '';

  // Check if native Web Share API is available
  const canNativeShare = typeof navigator !== 'undefined' && navigator.share;

  const handleNativeShare = async () => {
    if (!canNativeShare) return;

    const shareData: ShareData = {
      title,
      text: shareText,
      url: shareUrl,
    };

    try {
      await navigator.share(shareData);
      setIsOpen(false);
    } catch (error) {
      // User cancelled sharing or error occurred
      console.error('Error sharing:', error);
    }
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast({
        title: 'Link copied!',
        description: 'Profile link has been copied to your clipboard.',
        duration: 3000,
      });

      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy link:', error);
      toast({
        title: 'Copy failed',
        description: 'Unable to copy link to clipboard.',
        variant: 'destructive',
        duration: 3000,
      });
    }
  };

  const getTwitterUrl = () => {
    const params = new URLSearchParams({
      url: shareUrl,
      text: `${shareText} ${hashtagString}`.trim(),
      via: 'afinewinedynasty',
    });
    return `https://twitter.com/intent/tweet?${params.toString()}`;
  };

  const getLinkedInUrl = () => {
    const params = new URLSearchParams({
      url: shareUrl,
      title: title,
      summary: shareText,
    });
    return `https://www.linkedin.com/sharing/share-offsite/?${params.toString()}`;
  };

  const getRedditUrl = () => {
    const params = new URLSearchParams({
      url: shareUrl,
      title: title,
    });
    return `https://www.reddit.com/submit?${params.toString()}`;
  };

  const openShareWindow = (url: string) => {
    window.open(
      url,
      'share',
      'width=600,height=400,scrollbars=yes,resizable=yes,toolbar=no,menubar=no'
    );
    setIsOpen(false);
  };

  const buttonSize = {
    sm: 'h-8 px-3 text-sm',
    md: 'h-9 px-4',
    lg: 'h-10 px-6',
  }[size];

  const iconSize = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5',
  }[size];

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size={size}
          className={`${buttonSize} ${className}`}
        >
          <Share2 className={`${iconSize} mr-2`} />
          Share
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80" align="end">
        <Card className="border-0 shadow-none">
          <CardContent className="p-0 space-y-4">
            <div>
              <h4 className="font-semibold text-gray-900 mb-1">
                Share this profile
              </h4>
              <p className="text-sm text-gray-600">{title}</p>
            </div>

            {/* Native Share (Mobile) */}
            {canNativeShare && (
              <Button
                onClick={handleNativeShare}
                variant="outline"
                className="w-full justify-start"
              >
                <Share2 className="h-4 w-4 mr-3" />
                Share via device
              </Button>
            )}

            {/* Social Media Platforms */}
            <div className="space-y-2">
              <Button
                onClick={() => openShareWindow(getTwitterUrl())}
                variant="outline"
                className="w-full justify-start"
              >
                <Twitter className="h-4 w-4 mr-3 text-blue-400" />
                Share on Twitter
              </Button>

              <Button
                onClick={() => openShareWindow(getLinkedInUrl())}
                variant="outline"
                className="w-full justify-start"
              >
                <Linkedin className="h-4 w-4 mr-3 text-blue-600" />
                Share on LinkedIn
              </Button>

              <Button
                onClick={() => openShareWindow(getRedditUrl())}
                variant="outline"
                className="w-full justify-start"
              >
                <ExternalLink className="h-4 w-4 mr-3 text-orange-500" />
                Share on Reddit
              </Button>
            </div>

            {/* Copy Link */}
            <div className="border-t pt-4">
              <div className="flex items-center space-x-2">
                <div className="flex-1 p-2 bg-gray-50 rounded text-sm text-gray-600 truncate">
                  {shareUrl}
                </div>
                <Button
                  onClick={handleCopyLink}
                  variant="outline"
                  size="sm"
                  className="flex-shrink-0"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            {/* Hashtags */}
            {hashtags.length > 0 && (
              <div className="border-t pt-4">
                <p className="text-xs text-gray-500 mb-2">
                  Suggested hashtags:
                </p>
                <div className="flex flex-wrap gap-1">
                  {hashtags.map((tag, index) => (
                    <Badge key={index} variant="secondary" className="text-xs">
                      #{tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </PopoverContent>
    </Popover>
  );
}
