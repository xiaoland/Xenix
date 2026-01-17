CREATE TABLE "ml_backend_workers" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"created_by" uuid,
	"adapter" text NOT NULL,
	"adapter_params" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"is_default" boolean DEFAULT false NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "ml_backend_workers_name_unique" UNIQUE("name"),
	CONSTRAINT "ml_backend_workers_adapter_check" CHECK ("adapter" IN ('aliyun-fc', 'spawn'))
);
--> statement-breakpoint
ALTER TABLE "ml_backend_workers" ADD CONSTRAINT "ml_backend_workers_created_by_users_id_fk" FOREIGN KEY ("created_by") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_ml_backend_workers_adapter" ON "ml_backend_workers" ("adapter");--> statement-breakpoint
CREATE INDEX "idx_ml_backend_workers_default" ON "ml_backend_workers" ("is_default") WHERE "is_default" = true;--> statement-breakpoint
ALTER TABLE "tasks" ADD COLUMN "ml_backend_worker_id" integer;--> statement-breakpoint
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_ml_backend_worker_id_ml_backend_workers_id_fk" FOREIGN KEY ("ml_backend_worker_id") REFERENCES "public"."ml_backend_workers"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_tasks_worker" ON "tasks" ("ml_backend_worker_id");--> statement-breakpoint
INSERT INTO "ml_backend_workers" ("name", "adapter", "adapter_params", "is_default", "is_active")
VALUES
	('local-spawn', 'spawn', '{"basePath": "/tmp/ml-backend"}'::jsonb, true, true),
	('aliyun-fc-prod', 'aliyun-fc', '{"serviceName": "xenix", "timeout": 60000, "basePath": "/mnt/oss"}'::jsonb, false, true);
