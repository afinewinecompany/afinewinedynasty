"""
Populate the social_mentions table with sample data for prospects
"""
from app.db.database import SyncSessionLocal
from app.models.hype import SocialMention, PlayerHype
from datetime import datetime, timedelta
import random

def populate_social_mentions():
    db = SyncSessionLocal()

    try:
        # Get all player hype records
        players = db.query(PlayerHype).all()
        print(f"Found {len(players)} players")

        platforms = ['twitter', 'bluesky', 'reddit', 'instagram']
        sentiments = ['positive', 'neutral', 'negative']

        # Sample content templates for different platforms
        twitter_templates = [
            "{player} is looking great in spring training! Future superstar 🔥",
            "Just watched {player}'s highlights. This kid is gonna be special.",
            "{player} with another clutch hit! Can't wait to see them in the majors",
            "Hot take: {player} will be ROY next season",
            "{player}'s swing is absolutely gorgeous. Top 5 prospect for a reason",
            "Anyone else hyped about {player}? The future is bright!",
            "{player} just made the play of the year in AAA",
            "Reminder that {player} is only 20 years old. Insane talent.",
        ]

        bluesky_templates = [
            "Watching {player} develop has been a joy. Genuine 5-tool potential.",
            "{player} update: 3-4 with 2 RBIs today. This prospect is the real deal.",
            "The hype around {player} is totally justified. Elite bat speed.",
            "{player} just hit a moonshot. 450+ feet easy.",
            "Can we talk about how good {player} is at reading pitchers?",
        ]

        reddit_templates = [
            "{player} Discussion Thread - What are your thoughts on their MLB ETA?",
            "Just got back from watching {player} play. AMA!",
            "{player} is criminally underrated in the prospect rankings",
            "Film breakdown: Why {player}'s approach at the plate is elite",
            "[Highlight] {player} makes an incredible defensive play",
            "{player} promoted to AAA! Championship window opening soon?",
        ]

        instagram_templates = [
            "⚾️ {player} showing off that power stroke! 💪 #ProspectWatch",
            "{player} is built different 🔥 Future star in the making",
            "Your daily reminder that {player} is HIM 👑",
            "POV: Watching {player} take BP 🎯⚡️",
        ]

        handles = {
            'twitter': ['BaseballProspects', 'MLBPipeline', 'ProspectInsider', 'FutureStars', 'ScoutingReport', 'DiamondDigest'],
            'bluesky': ['baseball.scout', 'prospect.analyst', 'mlb.futures', 'farm.report', 'top.prospects'],
            'reddit': ['r/baseball', 'r/fantasybaseball', 'r/MLBDraft', 'ProspectWatch', 'MinorLeagueBall'],
            'instagram': ['mlb_prospects', 'future_stars_bb', 'prospect_hype', 'baseball_pipeline', 'top100_prospects'],
        }

        templates_by_platform = {
            'twitter': twitter_templates,
            'bluesky': bluesky_templates,
            'reddit': reddit_templates,
            'instagram': instagram_templates,
        }

        mentions_created = 0

        # Create 3-10 mentions for each player
        for player in players:
            num_mentions = random.randint(3, 10)

            for _ in range(num_mentions):
                platform = random.choice(platforms)
                template = random.choice(templates_by_platform[platform])
                content = template.format(player=player.player_name)

                # Create realistic engagement based on platform
                if platform == 'twitter':
                    likes = random.randint(50, 5000)
                    shares = random.randint(5, 500)
                elif platform == 'bluesky':
                    likes = random.randint(20, 1000)
                    shares = random.randint(2, 100)
                elif platform == 'reddit':
                    likes = random.randint(100, 10000)
                    shares = random.randint(10, 1000)
                else:  # instagram
                    likes = random.randint(100, 20000)
                    shares = random.randint(5, 200)

                # Sentiment weighted towards positive for high HYPE players
                if player.hype_score > 70:
                    sentiment = random.choices(sentiments, weights=[0.7, 0.2, 0.1])[0]
                elif player.hype_score > 40:
                    sentiment = random.choices(sentiments, weights=[0.5, 0.3, 0.2])[0]
                else:
                    sentiment = random.choices(sentiments, weights=[0.3, 0.4, 0.3])[0]

                # Random timestamp within last 7 days
                days_ago = random.randint(0, 7)
                hours_ago = random.randint(0, 23)
                posted_at = datetime.now() - timedelta(days=days_ago, hours=hours_ago)

                # Generate unique post_id
                post_unique_id = f"{platform}_{player.player_id}_{random.randint(100000, 999999)}"

                mention = SocialMention(
                    player_hype_id=player.id,
                    platform=platform,
                    post_id=post_unique_id,
                    author_handle=random.choice(handles[platform]),
                    content=content,
                    url=f"https://{platform}.com/post/{random.randint(100000, 999999)}",
                    likes=likes,
                    shares=shares,
                    sentiment=sentiment,
                    posted_at=posted_at,
                    collected_at=datetime.now()
                )

                db.add(mention)
                mentions_created += 1

        db.commit()
        print(f"Successfully created {mentions_created} social mentions for {len(players)} players")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    populate_social_mentions()
