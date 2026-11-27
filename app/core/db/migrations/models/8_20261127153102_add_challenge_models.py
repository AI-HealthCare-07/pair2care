from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `challenge_templates` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `title` VARCHAR(100) NOT NULL,
    `category` VARCHAR(30) NOT NULL COMMENT 'WALK: WALK\nWATER: WATER\nEXERCISE: EXERCISE\nSTRETCH: STRETCH\nLESS_ALCOHOL: LESS_ALCOHOL\nWEIGHT: WEIGHT\nNO_SMOKING: NO_SMOKING',
    `default_times_per_week` INT NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `pairs` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `invite_code` VARCHAR(128) NOT NULL UNIQUE,
    `pair_key` VARCHAR(50) UNIQUE,
    `status` VARCHAR(8) NOT NULL COMMENT 'PENDING: PENDING\nACCEPTED: ACCEPTED\nENDED: ENDED' DEFAULT 'PENDING',
    `accepted_at` DATETIME(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `partner_id` BIGINT,
    `requester_id` BIGINT NOT NULL,
    CONSTRAINT `fk_pairs_users_a27c21a8` FOREIGN KEY (`partner_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_pairs_users_fe96ac01` FOREIGN KEY (`requester_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `challenges` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `title` VARCHAR(100) NOT NULL,
    `times_per_week` INT NOT NULL,
    `starts_on` DATE NOT NULL,
    `ends_on` DATE,
    `status` VARCHAR(9) NOT NULL COMMENT 'ACTIVE: ACTIVE\nCOMPLETED: COMPLETED\nENDED: ENDED' DEFAULT 'ACTIVE',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `challenge_template_id` BIGINT,
    `created_by_id` BIGINT NOT NULL,
    `pair_id` BIGINT,
    CONSTRAINT `fk_challeng_challeng_0a8461bf` FOREIGN KEY (`challenge_template_id`) REFERENCES `challenge_templates` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_challeng_users_8750cf56` FOREIGN KEY (`created_by_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_challeng_pairs_4042a834` FOREIGN KEY (`pair_id`) REFERENCES `pairs` (`id`) ON DELETE SET NULL
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `challenge_participants` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `status` VARCHAR(7) NOT NULL COMMENT 'INVITED: INVITED\nJOINED: JOINED\nLEFT: LEFT' DEFAULT 'INVITED',
    `times_per_week` INT,
    `joined_at` DATETIME(6),
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `challenge_id` BIGINT NOT NULL,
    `user_id` BIGINT NOT NULL,
    UNIQUE KEY `uid_challenge_p_challen_7aab77` (`challenge_id`, `user_id`),
    CONSTRAINT `fk_challeng_challeng_c273d8e6` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_challeng_users_190147ad` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `challenge_checks` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `checked_on` DATE NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `challenge_id` BIGINT NOT NULL,
    `user_id` BIGINT NOT NULL,
    UNIQUE KEY `uid_challenge_c_challen_9fa29a` (`challenge_id`, `user_id`, `checked_on`),
    CONSTRAINT `fk_challeng_challeng_db15a945` FOREIGN KEY (`challenge_id`) REFERENCES `challenges` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_challeng_users_f6df0e75` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `challenge_checks`;
        DROP TABLE IF EXISTS `challenge_participants`;
        DROP TABLE IF EXISTS `challenges`;
        DROP TABLE IF EXISTS `pairs`;
        DROP TABLE IF EXISTS `challenge_templates`;"""


MODELS_STATE = (
    "eJztXWtz4ri2/SuufOqpm+4xBIJJ1f1AiDuhmwAHSM/0GaZcRlaIb8BmbNM9qVNzfvvVlv"
    "y27IDj8HSlitiytiwt67G1tLX1n7OFqeG5/amFLR09nV0J/zkz1AUmF7En58KZulwG4RDg"
    "qNM5jaoGcaa2Y6nIIaGP6tzGJEjDNrL0paObBgk1VvM5BJqIRNSNWRC0MvS/VlhxzBl2nr"
    "BFHvzxJwnWDQ3/jW3vdvmsPOp4rkWyqmvwbhquOC9LGtYxnM80IrxtqiBzvloYQeTli/Nk"
    "Gn5s3XAgdIYNbKkOhuQdawXZh9y55fRKxHIaRGFZDMlo+FFdzZ1QcdfEAJkG4EdyY9MCzu"
    "AtH6uVWqMmXVzWJBKF5sQPafzDiheUnQlSBHrjs3/oc9VRWQwKY4DbD2zZkKUEeO0n1eKj"
    "FxKJQUgyHofQAywLQy8gADGoOAWhuFD/VubYmDlQwav1egZm31rD9l1r+IHE+gVKY5LKzO"
    "p4z31UZc8A2ABIaBobgOhGP0wAK6K4BoAkViqA9FkUQPJGB7M2GAXxy6jf44MYEokB+WCQ"
    "Av6h6cg5F+a67fy5n7BmoAilhkwvbPuveRi8D/et3+O4trv9a4qCaTszi6ZCE7gmGEOX+f"
    "gcavwQMFXR80/V0pTEE7NqpsVNPlpUF/EQ1VBnFCsoMZTPHUQebNqhJwYXGp45tKxIDHu/"
    "RpZrfXZEg0uzWr24aFTFi0upXms06pLojzLJR1nDzXXnFkacSN18fQjCC1Wfb9J3+gLF9J"
    "7vjvL7Dz5Pqv2ENWWp2vZP0+JU2HQwOaIHOihVpXUGpaqUPijBsyiwho6e6fUGiIZlDhPK"
    "+jrDez19dK8nBndSYo3180kUZWO1oEh2SJZUA+EEooH0jvE8u2915SsBfifGZ5ndsf9nOX"
    "C+XAPmy1SUL+MgT3XLedLUlyTMNwQcfmUNy8TAJR02dvQF/gQX+1ltM/C7aY3lGD5/rXTs"
    "KKSOWRwtc0xKyocoJpaGEvysgZI7uOwHSOPOPa24ixdXyYSAjCrH+s6wlgkC439zgSaNdn"
    "OYXaES5FdBtvAsdeL+epcaSOfqUgsD+Gwk9x+6V8JkhSoVRH4vp9LEuH4YtXoQONUkkQSK"
    "U3Fi3LTk2wcaeCGSQFW7RBOj02vfyX0aFzUaEvlFTRJ8+1urd/uFxla1SoUES4+IJvHFjc"
    "0SQZJYmxgPXfd19O3u60byl37vluXsAkIlqU4S/k7kb287NGU01cgvviCxb8n7fmMpq6hS"
    "h6Q0Ety+e+jdXj98pcloapOWqOKG91r3oXBRJQWH3HnRIWtudAj2YrNgGptlxo3PcsPisw"
    "euhPvATZ+BgiQKNgElz7hVWW/6nzH7jw9duq2QiZ3+g6NoXZvmHKtGymQrLBeryVMi+F7D"
    "lj9FKLqzuO73u5Fp/3UnNqHqPdxfywReii6JpDuReVYUU22hc7qIVyH1xLaI6KYz+p1AOl"
    "dtR5mbMx6oN+4YxUc1KpmlaR3qEDcat+4HEZxBBYMn1cjo54UmRkA/EeG3zvhOgFvh3/2e"
    "zBsNaTwYEskzdeWYimH+JNU2XGwv2AuKko0WBmgVlaMJZn/IqGQBH3IXsz1SBq1vzF/cen"
    "QgX9at8pkfdrXUcn7YqGT5YXf6YWnmN2CuQxXAxpYCsGDAJDn0ueKfvw7xXHX4OnCImm6z"
    "lPbzc//j1WEvNPjsIW4Qq3PnSVla5qM+x2+E5I4mNmBpHTAo6Amj59VSsTAyLe2NoLRZYk"
    "Oa1gGDYun2M6knGJbNSPpvRGVIUhv4iR0wLG4DIspbIY2na84OGAxoMIsFNjS1iCoSSeyA"
    "UZnPF8rKVme4gFrSnS8eIKn16snOpgHZgCxV3VJ044fuFFFPBiS1A8fCwiRP9ls1kjWB2N"
    "dm4s2d0JM6BzLprdpI20vnkDHxyqAsVcvRkb4sosX4yAy8RA9ahw1AoopbUeBQxe3AYHlv"
    "Gx1vwpNiqhOaD2Vb7ETmYKXlzlFa7qhkfo8XXKO99VahIgnsem1/LA/vR1cC/TcxBsPOt1"
    "b7+5XgXsCCUG/UGXe+ycqd3OqO766EeEiutZR1jAAq6auFlYQZwEma9K6zIlVNX5Gqclek"
    "oHby+pDXlk98uS2un7wbt1/g8knJuh8FOcth3WHA33S4DQm9PubuySfc2rCb4L6jYCeR/m"
    "xaWJ8ZX/FLYshNZ7f3E+U03ZcEW+pPX9ELVyBSPFIozDqedmvUbt3IZ//sxtI9ypFz9OgE"
    "iZ6uSXPI+1d16TOwWKmCkcj0QhImK61eR2DwgiRJ+N/gXqtLTeEDmM2oKCwBpjGoBjYiIp"
    "LceBDrgsSaSlQUXVQuIKiGzuGuWqHmMZU63NTRJXv0y6e4OrQ3GZsY5G+FHuuQck1DzGin"
    "Sh+LAmT5V3tl/cAvHxfk05DMf1pokCNVuwSDHxIL7HvEihBPRHuUPMsiyNG54MWeVkR4cv"
    "kI+WeF0eqQGC0SuRPFaUOSpEiKQbEkaqvUUOuQd3l4Azd1SXB044U0D4iBMURvPCK3EGPT"
    "ckzdxlBwTRQqAHOlRo2kyK9WnUrMCqjOYKJw1vz3qkgUA8zq05owWpA5s9eV+xmb1i5FCg"
    "xBj37JJn2FWBMq/236hXKzlMSHfgnOd4YsM4MwmomaxECbkt9qsyb42Klq008bNVGFWUd5"
    "VSiUrUcopqhCctVKs0qNrurw0ioWg+ik/kH2xKbkI8BeRCoc/daXgBAzwPLqrqrSEjUonA"
    "2pDgWr1gET8gJ41ITCTWs0ZYlWAlaESKbcMpK3SazZvD7r/SPc/YXUoz/L6fCupsPPOs/i"
    "db2ZsCe760lwv3fdbw1vOmD5GFxPjN9k+WuXzIbZf9IJ3XTGVwL85pr0Fm5AyPprJcfcNy"
    "lZToG9hU999uQoaMGZrWGkkxEhZUtRWC4+V2OCn9wE9hPYrG0Fcrtz3+p+qJ3Hp7sexLUE"
    "jj8ZHs+zDXGMyJU4nv1UdTtHdQyLvRnFvTK7zAPiowoKhaLp6pRMl2zliYBjWpw9QxGNLw"
    "FqRjIHNpm/qDYufTUBbrIUgxGBu5skthZmIaBmJHOCoNr6dE5e9WZUs9I5QVjdlvtE4loO"
    "NkDpeWMnkJbUCYLrtuAiwH0lqRME12vIRaD7WlonCK86R+aTOVfwDx6/nA1nXPaE4Xukpl"
    "4G2rhKchM4YSDVhbnimRash2IgfYIQTnWwlcpdEzniJwiivTCfYYiY64/+qvJGQwxH/oRh"
    "RCvL4poKrYdiSPwEQUT6TLWwA7OXJcwQeU4+snHkp3CCUD6xpRLHnKoImZvCmJQ+QQjnJN"
    "O6pmBSpzbFLyZ6guDpdnTSoenqzDDtPIZm6emUhmdxzH325w1489MosY5jvbTwzFB5Y/1r"
    "CIcl8+G6VwR9aTtZ2k6el7aTpe3kMdlOlhvGt7wtK+pfgGNQmnBAkG5QynF8sI5BKbNiZJ"
    "7NVER9sjWpLaaKpuCLDVHDwyYSAzNOMFeMm3XyTEKLSto16mQ2n7gesrRjNnq1OjUTrFRJ"
    "opqoaZ4tJCQNdnoIBWaBFQmBySTJFPKTQQ1qyVifgky9gVx7PeFDa9CJmSy6xRBVdC6oSx"
    "2sR2sfK8za0fU7V6XmnegxMB7VLkWafr0eWEo2mtRQVKx5L/DywuwFUV2k5peoqVXiVpON"
    "qRhJ1DWUDDkziORHpDaYzaYGMgg+iNagCVxURN9Q1LW09K1RPZNJ9+uQXKlQeGpTCeAGNr"
    "jse7hGo01cc61+ITa8DDzuCR9Irf2VdEs/dITtX4Nu5VdSFR1s6eqn5Us+60io80QBIpW5"
    "tI7cmXVk6CtwFdgU5TUideweau0X2zHnOlKmnMMkXuFJo6K5tMLtz50K5FXInDw3eHHZ00"
    "PvkQAANPtsvkKmvfFaB0f89DAs7RMLsE8kL5vNXxAZ77WNa2Fc9vSq4JM2V9CTOcc20ZhM"
    "zqkar6xuJMVPEMOpWkEbtmFf5jgb8MUGDdg2VxZKOTDj9X0wgfT2dmGc3bd6Dy1K1CaOe4"
    "AHcOAD/J8Y/fbwSiA/8WlsSp18z8MeSj74WPng0oPtMXzYhA+rkuc/L3n+kufPwfPvkV/H"
    "96T5Y7hweP4kculEP++breU6gjHGuFrheGhATdjTrl1SNhehWtJpAz0NBZhe4Ncv1WamHw"
    "aPHK9/FJmzgPrHCtdrxK7zBGsLH9m7gLquYkmYePk6o1y3FMuJy5V7PipqdCGiiagvAFyL"
    "Uebw5k9CNhfve79wnRUEeWYOGEILJ+tz7r+wYqVKe34g2NIH87ShNkIQR4oMjibu+zdy18"
    "vl/wjtO7n99WGgtIedsTzstLwnVba48klg7iIgVAs5+NCavqsKuuIRTpXhmGMZQNNtrDJu"
    "qvSXsA8rAqEPkmeqGBLftdeEu+8DeTgGb4BwBFT4bmLcdFrX8lgeXQneVZ7ZY6W6jseEas"
    "bZlvEJ5II0GjO3v4pAepvzdOgGeNN0CL9ivQScrRXtc64SvVCuD1C4n0YbEXV042UeT+j0"
    "eLk5/oFTzgl+vb76wrvuKrr9364E8kPqaethTPsL92Ji3HVu70j3QX7z1NAsSL0K2kitn4"
    "2kowDkmBZH108/jz0kUsB57HvFhBZ2HPt5XK3P47MmIbjbQxzX7w3e+Zhh3ViuHMU21KX9"
    "ZHL4s/Sqm5QsoAbvl73Bu1ThkoY+CrYySUNHDQU3Ji654oels2xldpR2TtfGgHPFS844C/"
    "GSkS8a3ZKRL4CRT+8UCsDvgA/wiwPJ7fFehzQ6MhUA6abH/+3PckYcUe6gHUF0JI+F3kO3"
    "u1vf2nA0WqpfbffctFd9ansnta21KLKWgT2sFngh0+ojW2do1NyD1s/Z+fJAaV9o7BnGEL"
    "NO/TJX6hINg3PqgXenOyD8hQsBuH5JqgsfhvK/Pt60RncfRbHyX1GssteKYp3vb/sgMs62"
    "bkT2KqCmxPxZB36ZJcz2PDBP19hfBJq4HqTdvRGR1R53E0J464aHQpVup6DLF+Il87INuz"
    "1QvaEFWx38RZZPkXz4kLmrIKTssF/EczutweYOhOued+rkDhG26UQTpzXmAjsFvIhf8vA6"
    "mLvaEuwEISN3sP0ky015yLk39fddZfteLqcic1YdiZxntwVpV6yHhFaLVXtllQstO15oCX"
    "+SXORpSH7X/Ol1t9+/UQZDeTR6GMpXQvR+YrD72+5Duz/yH7u3E6PVbffv+t0rwb2YGPLv"
    "8rDdgaje1cQYjeXB6Eqg/yZGu9+76bhMrXcJDrE7t3djcIgN/8l9q/tVuWl9J3L+JaQ0lH"
    "u34zv3SeSWPO2Mx53erXLXfxjC0/AtedqV5QEJhX+kXEO59fVza0Re6V+y9EduwqNcC0vF"
    "u43+oc5XnKqWaT/ryxypm+OKeF5d24KWglHNg2C1EAj3injPhSDJesqZdCmTejf+QdLoxb"
    "fg8LCdrIWZrG5M9DBp3QOhcb1iZ/K4C7zgOLnKWFpy4x9kU6iL6y0pZa0pJVpDucRxpEsc"
    "paX9UXzY0tK+5PX3gDzd09MIgZZeLLChqalW5dEY55lW5ZG473+2d4RZIi/3aQhHtYhQ6d"
    "Jjp7xS+IPk4ZXC8rvmlW5ane53pdVmRE/4bmLcy62u0uqO5WGvBcd9XwnxEOCDWuM7eaiM"
    "OwMghfybiTHsjL4q8u+DbgviQurxEO94NWUoD/rDsXfKmnubh9Up3lo1aHBcXYnfoiJCR+"
    "+8xVGdFcdecs2Nz770Fg2qB3IPjvc7SzYH98mV4F5MjMGw35ZHIxboXwM9ej/oymP5BuhR"
    "93JifCYNCILY/1xVuPAzAh3VfubqhQ8PnZu0CuyLxD7LaqVrn0BwL6fFGdBR3C5Y0w/r3b"
    "QssZmvaThcl+1j/Hea3VcgciAMQta8R/59HJnyJCwm/WlPt9+79aLHzSh5/hE2sqsOiZR2"
    "1bFqyzNKje193HguyJcvxHrxmBTDCGE83xjlkFAJbTq0MAnbiMD1BA6k/33vPQFLy1wsnT"
    "y7LJKSBwnpxTqQXqRDepGA1MKO9UKA4h7PlN6rRqW2x7KJb27z1UqtUZMuLmt+U/dDslp4"
    "6cX9SCnnci3hSD9suZZQriUc9lpCGE11hn0z51jt3cBfT3e+eICkXMPqvdN2duKsJwwKZ0"
    "0lhln6gsp8vlCiH+qd11MeiRqxshJeUM6FqMv00kHKlrrD84z1lb2YVh/T2BPxbxA0hDx8"
    "fUi8XLpKW7py3/+twxzjhG5I2q1bRb6/lm/YOkPkdj+WvLZMvexC69uKPwbHfMY8p4HpA0"
    "VM7CSpAnPl5AIvIXeS6CEVPWGFqjHA4G+MYqr8CaMJk/y8SMZkTxJFbDv6gqrVyLQdovZz"
    "NLvMPR78BI52v8fl2vs9dFuxVwhhmzfVfeXI0ZDgFk9y9ecr5ZGjJae5bbI6asW5+fI4T7"
    "yca+6bp5ljBndvSOT9oTvP1+SQAxce6V1CAfglrcoPFkluf7dXblHaT+ocpvF4jBfLuUoz"
    "xTklNh7pPPukWDe64rjx35+eLqnmXVHNju7w/Eulc12+wGFyXZW1dopWMnaKVjg7RUmBZ6"
    "b1kpdTDsvvmlQGJxbMlQX4thjLQ7gh/9I8ZgzlcfuOOaIgFxOjK49Giu9uI3yX9J3R6yuj"
    "+/5XygMH13lI4OJtnVycFJio2MqSjKk/MX7egP9IT+DAbANKI6hyXpmcVyY08XVME3zd4o"
    "2mCb5Kc1D65bsaJgxU3eJpfzQ8U+Fbkhiline8Kp5u/NAdTBDkHaybrujFxIrRS94d8djh"
    "KdI6yl5Vyjg+RUrYlZPmojzjFGUvxaI8JFOILfl2cSx+gfjI90y22m15QLdGeldEfe7dQA"
    "D9l0fFXacqp1fkRDVWEcLLfNpYTLQAdWyvVqL2Sfvyil3aoKe3kmPRqxM26OV86Si+a7LB"
    "LlXLMXKsDEXlysWhjJU3C5Py2U4OkOOSB8bW7HYRzgdveytxe7ydI16VXj+kwG3h5TpmvL"
    "PbeNmtJJ22QDoFkGStO6653lhyUMfLQZXLjAUsM+ZeiiqXoEK8k+XYG3oziwgduzczbGib"
    "4hMSeSM6e8UDHYerN9gQ9k3msJbsATCUbDcY35/bW1nL5hrdYDO1E2yWPrlPhBIpOcyj+L"
    "BJDjNhTZjjSNmUJEoCLIMA8/q76cvmgMdFD0xb3DLSdHF3cypXL3nczfnFoGqWBCOvpa5z"
    "DGq8Ny0ASa6J+d7V4LVRTRtw1thPsXTNrd4IqGe1dbAYhvq3N1C3wAHrSF+q8PZk/5qHvB"
    "0ESR5W24+1Yoyei4KEHmR8YGBshdUO15UsgjtWp9bZWxOv2cXy3n+E3sQaobcr7M+SEt8T"
    "SvwAuaRO71tn7PJAUTLJfXIluBcT40u/04MA9h/2hXwew36Qz7nOtciC36ORGqk0UmPfmP"
    "Sdae+FEen/Z+pGLromIliaDu7YdLDkU4+Cdiv51CP9sBl8an4atST19tRzx1Gjm8XqhS2F"
    "iqKi9hPvzTmodYm90ok23usDOWN0Sxaf4BMy6zAJARW0LQ7h3OWfiJLgncNZMgpbG6PSGY"
    "XQR+HqfGl6QVjq2M2bygnPUejFnJlsqRiXivFBolsqxptod6VifByK8T//D5bqzq0="
)
