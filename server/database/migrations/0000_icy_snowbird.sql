CREATE TABLE `datasets` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`dataset_id` text NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`file_path` text NOT NULL,
	`file_name` text NOT NULL,
	`file_size` integer,
	`columns` text,
	`row_count` integer,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `datasets_dataset_id_unique` ON `datasets` (`dataset_id`);--> statement-breakpoint
CREATE TABLE `logs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`timestamp` integer NOT NULL,
	`observed_timestamp` integer NOT NULL,
	`trace_id` text NOT NULL,
	`span_id` text,
	`severity_text` text NOT NULL,
	`severity_number` integer NOT NULL,
	`body` text NOT NULL,
	`resource` text,
	`attributes` text,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `model_metadata` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`category` text NOT NULL,
	`name` text NOT NULL,
	`label` text NOT NULL,
	`param_grid_schema` text,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `model_metadata_name_unique` ON `model_metadata` (`name`);--> statement-breakpoint
CREATE TABLE `model_results` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`task_id` text NOT NULL,
	`model` text NOT NULL,
	`params` text,
	`mse_train` text,
	`mae_train` text,
	`r2_train` text,
	`mse_test` text,
	`mae_test` text,
	`r2_test` text,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `tasks` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`task_id` text NOT NULL,
	`type` text NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`model` text,
	`dataset_id` text,
	`input_file` text,
	`output_file` text,
	`error` text,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `tasks_task_id_unique` ON `tasks` (`task_id`);