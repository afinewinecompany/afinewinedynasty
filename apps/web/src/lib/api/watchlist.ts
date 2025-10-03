/**
 * API client for watchlist operations
 *
 * @module WatchlistAPI
 * @version 1.0.0
 * @since 1.0.0
 */

import { apiClient } from './client';

export interface WatchlistEntry {
  id: number;
  prospect_id: number;
  prospect_name: string;
  prospect_position: string;
  prospect_organization: string | null;
  notes: string | null;
  added_at: string;
  notify_on_changes: boolean;
}

export async function addToWatchlist(
  prospectId: number,
  notes?: string,
  notifyOnChanges: boolean = true
): Promise<WatchlistEntry> {
  const response = await apiClient.post<WatchlistEntry>('/watchlist', {
    prospect_id: prospectId,
    notes,
    notify_on_changes: notifyOnChanges,
  });
  return response.data;
}

export async function getWatchlist(): Promise<WatchlistEntry[]> {
  const response = await apiClient.get<WatchlistEntry[]>('/watchlist');
  return response.data;
}

export async function removeFromWatchlist(prospectId: number): Promise<void> {
  await apiClient.delete(`/watchlist/${prospectId}`);
}

export async function updateWatchlistNotes(
  prospectId: number,
  notes: string
): Promise<void> {
  await apiClient.patch(`/watchlist/${prospectId}/notes`, { notes });
}

export async function toggleWatchlistNotifications(
  prospectId: number,
  enabled: boolean
): Promise<void> {
  await apiClient.patch(`/watchlist/${prospectId}/notifications`, { enabled });
}
