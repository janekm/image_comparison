import asyncio
import fal_client

async def submit():
    handler = await fal_client.submit_async(
        "fal-ai/aura-flow",
        arguments={
            "prompt": "Close-up portrait of a majestic iguana with vibrant blue-green scales, piercing amber eyes, and orange spiky crest. Intricate textures and details visible on scaly skin. Wrapped in dark hood, giving regal appearance. Dramatic lighting against black background. Hyper-realistic, high-resolution image showcasing the reptile's expressive features and coloration."
        },
    )

    log_index = 0
    async for event in handler.iter_events(with_logs=True):
        if isinstance(event, fal_client.InProgress):
            new_logs = event.logs[log_index:]
            for log in new_logs:
                print(log)
                print(log["message"])
            log_index = len(event.logs)

    result = await handler.get()
    print(result)


if __name__ == "__main__":
    asyncio.run(submit())