/**
 * Watchlist card component displaying single prospect entry
 *
 * @component WatchlistCard
 * @version 1.0.0
 * @since 1.0.0
 */

import React from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { WatchlistEntry } from '@/lib/api/watchlist';

interface WatchlistCardProps {
  entry: WatchlistEntry;
  onRemove: (prospectId: number) => Promise<void>;
  onUpdateNotes: (prospectId: number, notes: string) => Promise<void>;
}

export const WatchlistCard: React.FC<WatchlistCardProps> = ({
  entry,
  onRemove,
  onUpdateNotes,
}) => {
  const [isEditing, setIsEditing] = React.useState(false);
  const [notes, setNotes] = React.useState(entry.notes || '');

  const handleSaveNotes = async (): Promise<void> => {
    await onUpdateNotes(entry.prospect_id, notes);
    setIsEditing(false);
  };

  return (
    <Card className="p-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-lg font-semibold">{entry.prospect_name}</h3>
          <p className="text-sm text-gray-600">
            {entry.prospect_position} - {entry.prospect_organization}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Added: {new Date(entry.added_at).toLocaleDateString()}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onRemove(entry.prospect_id)}
        >
          Remove
        </Button>
      </div>

      <div className="mt-4">
        {isEditing ? (
          <div>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full p-2 border rounded"
              rows={3}
            />
            <div className="flex gap-2 mt-2">
              <Button size="sm" onClick={handleSaveNotes}>
                Save
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setIsEditing(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-sm">{entry.notes || 'No notes'}</p>
            <Button
              size="sm"
              variant="link"
              onClick={() => setIsEditing(true)}
              className="p-0 h-auto mt-1"
            >
              Edit notes
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
};
