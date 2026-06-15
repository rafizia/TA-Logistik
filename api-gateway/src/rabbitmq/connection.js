import amqp from "amqplib";
import dotenv from "dotenv";

dotenv.config();

const RABBITMQ_URL = process.env.RABBITMQ_URL;
let connection, channel;

export const initRabbitMQ = async () => {
  if (!connection) {
    let retries = 10;
    while (retries > 0) {
      try {
        console.log(`[INIT] Connecting to RabbitMQ at ${RABBITMQ_URL.replace(/:([^:@]+)@/, ":***@")}...`);
        connection = await amqp.connect(RABBITMQ_URL);
        
        connection.on("error", (err) => {
          console.error("[ERROR] RabbitMQ connection error:", err.message);
        });

        connection.on("close", () => {
          console.warn("[WARN] RabbitMQ connection closed. Node process might need restart or reconnection.");
        });

        channel = await connection.createChannel();
        
        channel.on("error", (err) => {
          console.error("[ERROR] RabbitMQ channel error:", err.message);
        });

        console.log("[DONE] RabbitMQ connected");
        break;
      } catch (err) {
        console.error(`[WAIT] RabbitMQ connection failed: ${err.message}. Retrying in 5 seconds... (${retries} retries left)`);
        retries -= 1;
        if (retries === 0) {
          throw new Error(`Failed to connect to RabbitMQ after multiple attempts: ${err.message}`);
        }
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }
  }
  return channel;
};

export const getChannel = () => {
  if (!channel) throw new Error("[NOT YET] RabbitMQ not initialized");
  return channel;
};

export const closeRabbitMQ = async () => {
  try {
    if (channel) await channel.close();
    if (connection) await connection.close();
  } catch (err) {
    console.error("[ERROR] Error closing RabbitMQ connection:", err.message);
  }
};
