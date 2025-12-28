DROP TABLE `model_results`;--> statement-breakpoint
DROP INDEX `tasks_task_id_unique`;--> statement-breakpoint
ALTER TABLE `tasks` ADD `parameter` text;--> statement-breakpoint
ALTER TABLE `tasks` ADD `result` text;--> statement-breakpoint
ALTER TABLE `tasks` ADD `started_at` integer;--> statement-breakpoint
ALTER TABLE `tasks` ADD `end_at` integer;--> statement-breakpoint
ALTER TABLE `tasks` DROP COLUMN `task_id`;--> statement-breakpoint
ALTER TABLE `tasks` DROP COLUMN `model`;--> statement-breakpoint
ALTER TABLE `tasks` DROP COLUMN `dataset_id`;--> statement-breakpoint
ALTER TABLE `tasks` DROP COLUMN `input_file`;--> statement-breakpoint
ALTER TABLE `tasks` DROP COLUMN `output_file`;--> statement-breakpoint
ALTER TABLE `tasks` DROP COLUMN `updated_at`;