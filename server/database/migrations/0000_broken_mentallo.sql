CREATE TABLE `datasets` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project_id` integer,
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
CREATE TABLE `projects` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `tasks` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`work_item_id` integer,
	`type` text NOT NULL,
	`parameter` text,
	`result` text,
	`status` text DEFAULT 'pending' NOT NULL,
	`error` text,
	`created_at` integer NOT NULL,
	`started_at` integer,
	`end_at` integer
);
--> statement-breakpoint
CREATE TABLE `work_items` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project_id` integer NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
