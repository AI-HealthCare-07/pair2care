from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `recommendations` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `rec_type` VARCHAR(16) NOT NULL COMMENT 'DAILY_ACTION: DAILY_ACTION\nMEAL_ALTERNATIVE: MEAL_ALTERNATIVE\nWEATHER_TIP: WEATHER_TIP\nRISK_EXPLANATION: RISK_EXPLANATION\nWEEKLY_REPORT: WEEKLY_REPORT',
    `target_on` DATE NOT NULL,
    `status` VARCHAR(10) NOT NULL COMMENT 'PENDING: PENDING\nPROCESSING: PROCESSING\nCOMPLETED: COMPLETED\nFAILED: FAILED' DEFAULT 'PENDING',
    `task_id` CHAR(36),
    `content` LONGTEXT,
    `sources` JSON,
    `risk_prediction_id` BIGINT UNIQUE,
    `meal_id` BIGINT UNIQUE,
    `model` VARCHAR(50),
    `prompt_version` VARCHAR(30),
    `retry_count` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_recommen_users_c1b33b7a` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_recommendat_user_id_d2f3da` (`user_id`, `rec_type`, `target_on`)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `llm_usage_logs` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `meal_id` BIGINT,
    `feature` VARCHAR(16) NOT NULL COMMENT 'DAILY_ACTION: DAILY_ACTION\nMEAL_ALTERNATIVE: MEAL_ALTERNATIVE\nWEATHER_TIP: WEATHER_TIP\nRISK_EXPLANATION: RISK_EXPLANATION\nWEEKLY_REPORT: WEEKLY_REPORT\nMEAL_VISION: MEAL_VISION\nRAG_EMBEDDING: RAG_EMBEDDING',
    `model` VARCHAR(50) NOT NULL,
    `input_tokens` INT NOT NULL DEFAULT 0,
    `output_tokens` INT NOT NULL DEFAULT 0,
    `cache_creation_tokens` INT NOT NULL DEFAULT 0,
    `cache_read_tokens` INT NOT NULL DEFAULT 0,
    `estimated_cost_usd` DECIMAL(10,6),
    `is_success` BOOL NOT NULL DEFAULT 1,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `recommendation_id` BIGINT,
    `user_id` BIGINT,
    CONSTRAINT `fk_llm_usag_recommen_00b39247` FOREIGN KEY (`recommendation_id`) REFERENCES `recommendations` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_llm_usag_users_1d678f84` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    KEY `idx_llm_usage_l_feature_163b9b` (`feature`, `created_at`),
    KEY `idx_llm_usage_l_user_id_78ebfb` (`user_id`, `created_at`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `llm_usage_logs`;
        DROP TABLE IF EXISTS `recommendations`;"""


MODELS_STATE = (
    "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"
    "n/o+XpLc/i6H6Ws6+f/6P7ZUpiA="
)
