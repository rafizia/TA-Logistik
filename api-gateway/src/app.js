import express from "express";
import { logHttpRequest } from "./config/logging.js";
import { errorMiddleware } from "./middlewares/error-middleware.js";
import { publicRouter } from "./routes/public-route.js";
import { restrictedRouter } from "./routes/restricted-route.js";
import cors from "cors";
import swaggerUi from "swagger-ui-express";
import { swaggerSpec } from "./config/swagger.js";

export const app = express();

const corsOptions = {
  origin: true,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
  optionsSuccessStatus: 200
};

app.use(cors(corsOptions));

app.options('*', cors(corsOptions));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(logHttpRequest);

app.use(publicRouter);

app.use("/api-docs", swaggerUi.serve, swaggerUi.setup(swaggerSpec));

app.use(restrictedRouter);

app.use((req, res, next) => {
  res.status(404).json({
    success: false,
    code: 404,
    message: "Not Found",
    data: null,
    error: `Cannot ${req.method} ${req.originalUrl}`,
  });
});

app.use(errorMiddleware);
